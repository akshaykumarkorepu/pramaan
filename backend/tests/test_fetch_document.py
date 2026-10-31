import asyncio

import httpx
import pytest

from pipeline import fetch_document as fd
from pipeline.fetch_document import fetch_document
from sources import http
from sources.errors import DomainNotAllowed, EmptyDocument, FetchFailed, PdfUnreadable

RBI_URL = "https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=1&Mode=0"
SEBI_URL = "https://www.sebi.gov.in/legal/circulars/oct-2026/x_1.html"
PIB_URL = "https://pib.gov.in/PressReleaseIframePage.aspx?PRID=1"
SEBI_PDF = "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1.pdf"


def make_pdf(lines):
    """A tiny valid PDF with one text line per entry (pdfminer rebuilds the missing xref table)."""
    ops = "BT /F1 11 Tf 14 TL 40 750 Td " + " ".join(f"({l.replace('(', '[').replace(')', ']')}) Tj T*" for l in lines) + " ET"
    return (
        "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
        "/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        f"4 0 obj<</Length {len(ops)}>>stream\n{ops}\nendstream endobj\n"
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        "trailer<</Root 1 0 R>>\n%%EOF\n"
    ).encode("latin-1")


PDF_LINES = [
    "CIRCULAR",
    "Subject: Rationalisation of KYC review for FPIs",
    "1. The KYC review periodicity is being increased for all FPIs and",
    "custodians shall comply with the revised timeline accordingly.",
    "2. Intermediaries must file the report by March 31, 2027 without",
    "fail and keep records of the filing for at least five years.",
    "Page 1 of 1",
]

RBI_HTML = """<html><head><title>Notifications | Official Website</title></head><body><nav>Home Menu</nav>
<table class="tablebg"><tr><td class="tableheader">(255 kb)</td>
<td class="tableheader">Know Your Customer Directions for NBFCs</td></tr></table>
<table class="td"><tr><td><script>var x = 1;</script>
<p>RBI/2026-27/1<br>DoR.X/2026</p><p>The Chairpersons/ CEOs of<br>All NBFCs</p>
<p>Please refer to the Directions dated November 28, 2025 and ensure compliance with them.</p>
<p>2. NBFCs shall complete the review by March 31, 2027.</p><p>2.1 Reviews shall be filed online.</p>
<footer>Copyright RBI</footer></td></tr></table></body></html>"""

SEBI_SHELL = (
    "<html><head><title>SEBI | X</title></head><body><h1>Rationalisation of KYC for FPIs</h1>"
    f"<iframe src='../../../web/?file={SEBI_PDF}'></iframe></body></html>"
)

PIB_HTML = """<html><body><h1>Scheme Title</h1><div id="PdfDiv"><table><tr><td>
<p>The Government has approved a new scheme to support small enterprises across the country.</p>
<p>It will benefit lakhs of workers and families in many states and union territories.</p>
<p>(रिलीज़ आईडी: 2330727)</p><p>Click here to see PDF</p><p>https://www.pib.gov.in/x</p><p>PIB Research</p>
</td></tr></table></div></body></html>"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    fd.clear_cache()

    async def instant(_):
        pass

    monkeypatch.setattr(http.asyncio, "sleep", instant)  # no real backoff in retry tests


class Site:
    """MockTransport serving {url: (status, headers, body)} and recording every request."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        url = str(request.url)
        self.calls.append(url)
        status, headers, body = self.pages.get(url, (404, {}, b"not found"))
        return httpx.Response(status, headers=headers, content=body)


def html(body):
    return (200, {"content-type": "text/html; charset=utf-8"}, body.encode())


def pdf(lines):
    return (200, {"content-type": "application/pdf"}, make_pdf(lines))


def run(url, site):
    return asyncio.run(fetch_document(url, transport=site.transport))


# ---------------------------------------------------------------- HTML

def test_rbi_html_title_numbering_and_noise_removed():
    doc = run(RBI_URL, Site({RBI_URL: html(RBI_HTML)}))
    assert doc.source == "rbi"
    assert doc.title == "Know Your Customer Directions for NBFCs"
    assert [p.id for p in doc.paragraphs] == ["p1", "p2", "p3", "2", "2.1"]
    assert doc.paragraphs[0].text == "RBI/2026-27/1 DoR.X/2026"  # <br> keeps words apart
    assert "var x" not in doc.full_text and "Copyright" not in doc.full_text and "Home Menu" not in doc.full_text
    assert doc.char_count == len(doc.full_text) and doc.pdf_url is None


def test_pib_body_cut_at_release_id_and_junk_dropped():
    doc = run(PIB_URL, Site({PIB_URL: html(PIB_HTML)}))
    assert doc.source == "pib" and doc.title == "Scheme Title"
    assert len(doc.paragraphs) == 2
    for junk in ("रिलीज़", "Click here", "PIB Research", "https://"):
        assert junk not in doc.full_text


def test_div_br_page_falls_back_to_line_splitting():
    page = "<html><body><table class='td'><tr><td>Dear Sir<br>1. First numbered duty that is long enough.<br>2. Second numbered duty that is also long enough.</td></tr></table></body></html>"
    doc = run(RBI_URL, Site({RBI_URL: html(page)}))
    assert [p.id for p in doc.paragraphs] == ["p1", "1", "2"]


# ---------------------------------------------------------------- PDF

def test_sebi_shell_reads_the_iframe_pdf():
    site = Site({SEBI_URL: html(SEBI_SHELL), SEBI_PDF: pdf(PDF_LINES)})
    doc = run(SEBI_URL, site)
    assert doc.source == "sebi" and doc.pdf_url == SEBI_PDF
    assert doc.title == "Rationalisation of KYC for FPIs"  # title still comes from the page
    assert [p.id for p in doc.paragraphs] == ["p1", "p2", "1", "2"]
    assert doc.paragraphs[2].text.endswith("accordingly.")  # wrapped line joined
    assert "Page 1 of 1" not in doc.full_text
    assert site.calls == [SEBI_URL, SEBI_PDF]


def test_direct_pdf_link_uses_subject_as_title():
    url = "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/A.PDF"
    doc = run(url, Site({url: pdf(PDF_LINES)}))
    assert doc.source == "rbi" and doc.title == "Rationalisation of KYC review for FPIs"
    assert doc.pdf_url == url


def test_thin_html_prefers_longer_pdf():
    thin = "<html><body><table class='td'><tr><td><p>Short notice text with a PDF attached below.</p><a href='/rdocs/a.PDF'>pdf</a></td></tr></table></body></html>"
    pdf_url = "https://www.rbi.org.in/rdocs/a.PDF"
    doc = run(RBI_URL, Site({RBI_URL: html(thin), pdf_url: pdf(PDF_LINES)}))
    assert "Intermediaries must file the report" in doc.full_text


def test_thin_html_keeps_html_when_pdf_is_shorter():
    body = "<p>" + "word " * 70 + "</p>"  # ~350 chars: thin, but longer than the PDF below
    page = f"<html><body><table class='td'><tr><td>{body}<a href='/rdocs/a.PDF'>pdf</a></td></tr></table></body></html>"
    pdf_url = "https://www.rbi.org.in/rdocs/a.PDF"
    short_pdf = ["Subject: A short PDF with a little text that is only just long enough to be accepted by", "the reader as readable text, nothing more than that, so it stays below the page text."]
    doc = run(RBI_URL, Site({RBI_URL: html(page), pdf_url: pdf(short_pdf)}))
    assert doc.full_text.startswith("word word")


def test_thin_rbi_html_survives_unreadable_pdf():
    thin = "<html><body><table class='td'><tr><td><p>Short notice text that is still real content for the reader.</p><a href='/rdocs/a.PDF'>pdf</a></td></tr></table></body></html>"
    pdf_url = "https://www.rbi.org.in/rdocs/a.PDF"
    doc = run(RBI_URL, Site({RBI_URL: html(thin), pdf_url: (200, {"content-type": "application/pdf"}, b"garbage")}))
    assert "Short notice text" in doc.full_text


def test_sebi_with_unreadable_pdf_raises():
    site = Site({SEBI_URL: html(SEBI_SHELL), SEBI_PDF: (200, {"content-type": "application/pdf"}, b"%PDF-1.4 broken")})
    with pytest.raises(PdfUnreadable) as e:
        run(SEBI_URL, site)
    assert e.value.kind == "pdf_unreadable" and e.value.url == SEBI_PDF


def test_image_only_pdf_is_unreadable():
    site = Site({SEBI_URL: html(SEBI_SHELL), SEBI_PDF: pdf(["x"])})  # almost no text, like a scan
    with pytest.raises(PdfUnreadable, match="no readable text"):
        run(SEBI_URL, site)


def test_pib_pdf_outside_allowed_hosts_is_skipped_and_html_text_kept():
    page = ("<html><body><h1>T</h1><div id='PdfDiv'><p>A short release with enough real text to be read on its own.</p>"
            "<a href='https://static.pib.gov.in/a.pdf'>pdf</a></div></body></html>")
    site = Site({PIB_URL: html(page)})
    doc = run(PIB_URL, site)
    assert "short release" in doc.full_text
    assert site.calls == [PIB_URL]  # the foreign-host PDF was never requested


def test_sebi_iframe_pointing_at_another_site_is_refused():
    shell = SEBI_SHELL.replace(SEBI_PDF, "https://evil.example/a.pdf")
    site = Site({SEBI_URL: html(shell)})
    with pytest.raises(PdfUnreadable, match="outside the accepted sites"):
        run(SEBI_URL, site)
    assert site.calls == [SEBI_URL]


# ---------------------------------------------------------------- errors, safety, cache

def test_disallowed_domain_refused_before_any_request():
    site = Site({})
    with pytest.raises(DomainNotAllowed):
        run("https://example.com/notice", site)
    assert site.calls == []


def test_redirect_to_other_site_is_blocked():
    site = Site({RBI_URL: (302, {"location": "https://evil.example/x"}, b""), "https://evil.example/x": html(RBI_HTML)})
    with pytest.raises(DomainNotAllowed):
        run(RBI_URL, site)
    assert "https://evil.example/x" not in site.calls


def test_not_found_is_a_readable_fetch_error_with_original_link():
    with pytest.raises(FetchFailed) as e:
        run(RBI_URL, Site({}))
    assert "HTTP 404" in str(e.value) and e.value.url == RBI_URL and e.value.kind == "fetch_failed"


def test_server_error_is_retried_then_reported():
    site = Site({RBI_URL: (503, {}, b"")})
    with pytest.raises(FetchFailed, match="retried 2 times"):
        run(RBI_URL, site)
    assert len(site.calls) == 3


def test_empty_page_raises_empty_document():
    with pytest.raises(EmptyDocument) as e:
        run(RBI_URL, Site({RBI_URL: html("<html><body><p>hi</p></body></html>")}))
    assert e.value.kind == "empty_document"


def test_second_call_is_served_from_cache():
    site = Site({RBI_URL: html(RBI_HTML)})
    first, second = run(RBI_URL, site), run(RBI_URL, site)
    assert len(site.calls) == 1
    assert second.fetched_at == first.fetched_at  # keeps the original fetch time for "fetched N min ago"


def test_failures_are_not_cached():
    run_fail = Site({})
    with pytest.raises(FetchFailed):
        run(RBI_URL, run_fail)
    assert run(RBI_URL, Site({RBI_URL: html(RBI_HTML)})).title.startswith("Know Your Customer")


def test_fragment_is_ignored_for_cache_key():
    site = Site({RBI_URL: html(RBI_HTML)})
    run(RBI_URL, site)
    run(RBI_URL + "#top", site)
    assert len(site.calls) == 1
