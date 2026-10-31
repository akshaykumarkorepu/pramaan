"""Only RBI, SEBI and PIB links are read. Exact hosts, not suffix matching, so look-alikes are refused."""
from urllib.parse import urlparse

from sources.errors import DomainNotAllowed

_HOSTS = {
    "rbi.org.in": "rbi",
    "rbidocs.rbi.org.in": "rbi",
    "sebi.gov.in": "sebi",
    "pib.gov.in": "pib",
}
ACCEPTED_SITES = "rbi.org.in, sebi.gov.in and pib.gov.in"


def _host(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
        host = parsed.hostname  # drops userinfo, so https://rbi.org.in@evil.com/ gives evil.com
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not host:
        return None
    return host.removeprefix("www.")


def source_of(url: str) -> str | None:
    host = _host(url)
    return _HOSTS.get(host) if host else None


def check_allowed(url: str) -> str:
    """Return the source id (rbi|sebi|pib) or raise DomainNotAllowed with a polite message."""
    source = source_of(url)
    if source:
        return source
    host = _host(url)
    where = f"That link is from {host}." if host else "That doesn't look like a web link."
    raise DomainNotAllowed(f"Pramaan reads only {ACCEPTED_SITES} notices. {where}", url)
