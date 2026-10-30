"""M1 page check: is the page reachable, how much body text, is there a PDF? M2's fetch_document reuses find_pdf_url."""
from dataclasses import dataclass
from urllib.parse import parse_qs, urljoin, urlparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from sources.http import get


@dataclass
class PageInfo:
    url: str
    status: int
    body_text_len: int
    pdf_url: str | None


def find_pdf_url(html: str, base_url: str) -> str | None:
    tree = HTMLParser(html)
    # SEBI: <iframe src="../../../web/?file=https://.../x.pdf">
    for node in tree.css("iframe[src]"):
        src = node.attributes.get("src") or ""
        file_param = parse_qs(urlparse(src).query).get("file")
        if file_param and ".pdf" in file_param[0].lower():
            return urljoin(base_url, file_param[0])
    # RBI and others: plain links to a PDF
    for node in tree.css("a[href]"):
        href = node.attributes.get("href") or ""
        if urlparse(href).path.lower().endswith(".pdf"):
            return urljoin(base_url, href)
    return None


def body_text_len(html: str) -> int:
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript"):
        node.decompose()
    body = tree.body
    return len(" ".join(body.text(separator=" ").split())) if body else 0


async def check_page(url: str, label: str) -> PageInfo:
    """Raises FetchError (user-readable) if the page can't be fetched."""
    resp = await get(url, label)
    return PageInfo(url, resp.status_code, body_text_len(resp.text), find_pdf_url(resp.text, str(resp.url)))
