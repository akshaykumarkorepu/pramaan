"""Typed document errors. `str(err)` is always safe to show to the user; `kind` is for the API/UI."""


class DocumentError(Exception):
    kind = "document_error"

    def __init__(self, message: str, url: str | None = None):
        super().__init__(message)
        self.url = url  # lets the UI offer a "read the original" link


class DomainNotAllowed(DocumentError):
    kind = "domain_not_allowed"


class FetchFailed(DocumentError):
    kind = "fetch_failed"


class PdfUnreadable(DocumentError):
    kind = "pdf_unreadable"


class EmptyDocument(DocumentError):
    kind = "empty_document"
