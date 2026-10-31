import pytest

from sources.allowlist import check_allowed, source_of
from sources.errors import DomainNotAllowed


@pytest.mark.parametrize("url,source", [
    ("https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=1&Mode=0", "rbi"),
    ("https://rbi.org.in/x", "rbi"),
    ("https://rbidocs.rbi.org.in/rdocs/notification/PDFs/A.PDF", "rbi"),
    ("https://www.sebi.gov.in/legal/circulars/oct-2026/a_1.html", "sebi"),
    ("http://sebi.gov.in/x", "sebi"),
    ("https://pib.gov.in/PressReleaseIframePage.aspx?PRID=1", "pib"),
    ("https://www.pib.gov.in/x", "pib"),
    ("  https://www.rbi.org.in/x  ", "rbi"),
])
def test_allowed(url, source):
    assert check_allowed(url) == source == source_of(url)


@pytest.mark.parametrize("url", [
    "https://example.com/x",
    "https://rbi.org.in.evil.com/x",      # suffix trick
    "https://evilrbi.org.in/x",           # prefix trick
    "https://rbi.org.in@evil.com/x",      # userinfo trick: real host is evil.com
    "https://static.pib.gov.in/a.pdf",    # subdomains are not on the list
    "ftp://www.rbi.org.in/x",
    "javascript:alert(1)",
    "www.rbi.org.in/no-scheme",
    "",
    "not a url at all",
])
def test_refused(url):
    assert source_of(url) is None
    with pytest.raises(DomainNotAllowed):
        check_allowed(url)


def test_refusal_names_accepted_sites_and_offending_host():
    with pytest.raises(DomainNotAllowed) as e:
        check_allowed("https://example.com/x")
    msg = str(e.value)
    assert "rbi.org.in" in msg and "sebi.gov.in" in msg and "pib.gov.in" in msg and "example.com" in msg
    assert e.value.kind == "domain_not_allowed"
