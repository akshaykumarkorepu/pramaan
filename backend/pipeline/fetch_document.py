"""fetch_document(url): an allowed RBI/SEBI/PIB link -> clean numbered paragraphs.

HTML first; if the page body is thin and a PDF exists (SEBI always), read the PDF instead.
Failures are typed (sources/errors.py) with messages that are safe to show the user."""
import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from typing import Literal, Optional
from urllib.parse import urldefrag, urlparse

import pdfplumber
from cachetools import TTLCache
from pydantic import BaseModel
from selectolax.lexbor import LexborHTMLParser

from api.schemas import Paragraph
from pipeline.paragraphs import assign_ids, split_text
from sources.allowlist import check_allowed
from sources.errors import DomainNotAllowed, EmptyDocument, FetchFailed, PdfUnreadable
from sources.feeds import LABELS
from sources.http import FetchError, get
from sources.pagecheck import find_pdf_url

log = logging.getLogger("pramaan.fetch_document")

THIN_HTML_CHARS = 500  # below this, prefer the PDF if there is one
MIN_DOC_CHARS = 50
MIN_PDF_CHARS = 200  # less than this from a PDF means scanned/image-only
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 150
BLOCK_COVERAGE = 0.7  # p/li/heading text must cover this share of the container, else split its lines

_cache: TTLCache = TTLCache(maxsize=128, ttl=30 * 60)


class FetchedDocument(BaseModel):
    title: str
    url: str
    source: Literal["rbi", "sebi", "pib"]
    fetched_at: datetime
    paragraphs: list[Paragraph]
    full_text: str
    pdf_url: Optional[str] = None
    from_pdf: bool = False  # the paragraphs were read from a PDF (pdf_url alone only says the page links to one)
    char_count: int


def clear_cache() -> None:
    _cache.clear()


# ---------------------------------------------------------------- HTML

_KB_ONLY = re.compile(r"^\(\s*[\d.,]+\s*kb\s*\)$", re.I)
_PIB_END = re.compile(r"रिलीज़ आईडी|Release ID", re.I)
_PIB_JUNK = re.compile(r"^(https?://\S+|click here.*|pib research|\*+)$", re.I)
_NOISE_TAGS = "script, style, noscript, nav, footer, aside"


def _container(tree: LexborHTMLParser, source: str):
    selectors = {"rbi": ("table.td", "#pnlDetails"), "pib": ("#PdfDiv",)}.get(source, ())
    for sel in (*selectors, "main", "article", "body"):
        node = tree.css_first(sel)
        if node is not None:
            return node
    return None


def _title(tree: LexborHTMLParser, source: str) -> str:
    if source == "rbi":
        # RBI has two table headers: the title and a "(255 kb)" PDF size label
        for n in tree.css("td.tableheader"):
            t = " ".join(n.text().split())
            if len(t) > 8 and not _KB_ONLY.match(t):
                return t
    h1 = tree.css_first("h1")
    if h1 is not None and h1.text(strip=True):
        return " ".join(h1.text().split())
    t = tree.css_first("title")
    return " ".join(t.text().split()) if t is not None else ""


def _html_paragraphs(tree: LexborHTMLParser, source: str) -> list[Paragraph]:
    box = _container(tree, source)
    if box is None:
        return []
    for n in box.css(_NOISE_TAGS):
        n.decompose()
    blocks = []
    for n in box.css("h1, h2, h3, h4, p, li"):
        if n.tag == "li" and n.css_first("p") is not None:
            continue  # its <p> is collected on its own
        t = " ".join(n.text(separator=" ").split())  # separator keeps <br>-separated words apart
        if t:
            blocks.append(t)
    if source == "pib":
        cut = next((i for i, b in enumerate(blocks) if _PIB_END.search(b)), len(blocks))
        blocks = [b for b in blocks[:cut] if not _PIB_JUNK.match(b)]
    whole = " ".join(box.text(separator=" ").split())
    # Some pages keep text in bare <div>/<td> + <br>; if p/li blocks miss most of it, split the raw lines instead.
    if source != "pib" and sum(map(len, blocks)) < BLOCK_COVERAGE * len(whole):
        return split_text(box.text(separator="\n"))
    return assign_ids(blocks)


# ---------------------------------------------------------------- PDF

def _pdf_pages(data: bytes) -> list[str]:
    """Blocking (pdfminer). Run in a thread."""
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise PdfUnreadable(f"This PDF has {len(pdf.pages)} pages, more than the {MAX_PDF_PAGES} Pramaan reads.")
        return [p.extract_text() or "" for p in pdf.pages]


async def _pdf_paragraphs(data: bytes, url: str) -> list[Paragraph]:
    if len(data) > MAX_PDF_BYTES:
        raise PdfUnreadable("This PDF is too large for Pramaan to read.", url)
    try:
        pages = await asyncio.to_thread(_pdf_pages, data)
    except PdfUnreadable as e:
        e.url = url
        raise
    except Exception:
        log.exception("pdf parse failed for %s", url)
        raise PdfUnreadable("Couldn't read this PDF. Open the original document instead.", url)
    text = "\n".join(pages)
    if len(text.strip()) < MIN_PDF_CHARS:
        raise PdfUnreadable("This PDF has no readable text (it may be a scan). Open the original document instead.", url)
    return split_text(text)


# ---------------------------------------------------------------- main

def _is_pdf(resp, url: str) -> bool:
    return (
        "pdf" in resp.headers.get("content-type", "").lower()
        or urlparse(url).path.lower().endswith(".pdf")
        or resp.content[:5] == b"%PDF-"
    )


def _chars(paras: list[Paragraph]) -> int:
    return sum(len(p.text) for p in paras)


async def _fetch(url: str, source: str, transport):
    try:
        # host_check also runs on redirect hops, so an allowed host can't bounce us elsewhere
        return await get(url, LABELS[source], transport=transport, host_check=check_allowed)
    except FetchError as e:
        raise FetchFailed(f"{e}. Open the original link instead.", url)


async def _fetch_pdf(pdf_url: str, source: str, transport) -> list[Paragraph]:
    try:
        resp = await _fetch(pdf_url, source, transport)
    except DomainNotAllowed:
        # e.g. PIB attachments sit on static.pib.gov.in, which is outside the accepted sites
        raise PdfUnreadable("The PDF for this notice is hosted outside the accepted sites, so Pramaan can't read it.", pdf_url)
    return await _pdf_paragraphs(resp.content, pdf_url)


def _pdf_title(paras: list[Paragraph], url: str) -> str:
    for p in paras:
        m = re.match(r"^Subject\s*:\s*(.+)", p.text, re.I)
        if m:
            return m.group(1)[:200]
    return paras[0].text[:120] if paras else urlparse(url).path.rsplit("/", 1)[-1]


async def fetch_document(url: str, *, transport=None) -> FetchedDocument:
    """`transport` is only for tests (httpx.MockTransport)."""
    url = urldefrag(url.strip())[0]
    source = check_allowed(url)  # raises DomainNotAllowed before any network call
    cached = _cache.get(url)
    if cached is not None:
        return cached

    resp = await _fetch(url, source, transport)
    pdf_url: str | None = None
    from_pdf = False

    if _is_pdf(resp, url):
        pdf_url = str(resp.url)
        from_pdf = True
        paras = await _pdf_paragraphs(resp.content, url)
        title = _pdf_title(paras, url)
    else:
        tree = LexborHTMLParser(resp.text)
        title = _title(tree, source)
        paras = _html_paragraphs(tree, source)
        pdf_url = find_pdf_url(resp.text, str(resp.url))
        if pdf_url and _chars(paras) < THIN_HTML_CHARS:
            try:
                pdf_paras = await _fetch_pdf(pdf_url, source, transport)
            except PdfUnreadable:
                # SEBI's HTML is only a shell around the PDF, so there is nothing to fall back to
                if source == "sebi" or not paras:
                    raise
            else:
                if _chars(pdf_paras) > _chars(paras):
                    paras = pdf_paras
                    from_pdf = True

    full_text = "\n\n".join(p.text for p in paras)
    if len(full_text) < MIN_DOC_CHARS:
        raise EmptyDocument("This page has no readable notice text. Open the original link instead.", url)

    doc = FetchedDocument(
        title=title or _pdf_title(paras, url),
        url=url,
        source=source,
        fetched_at=datetime.now(timezone.utc),
        paragraphs=paras,
        full_text=full_text,
        pdf_url=pdf_url,
        from_pdf=from_pdf,
        char_count=len(full_text),
    )
    _cache[url] = doc
    return doc
