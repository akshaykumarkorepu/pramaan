from sources.pagecheck import body_text_len, find_pdf_url

BASE = "https://www.sebi.gov.in/legal/circulars/oct-2026/a_1.html"


def test_sebi_iframe_pdf():
    html = "<iframe src='../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1.pdf' width='100%'></iframe>"
    assert find_pdf_url(html, BASE) == "https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1.pdf"


def test_anchor_pdf_made_absolute():
    html = '<a href="/rdocs/a.PDF">pdf</a>'
    assert find_pdf_url(html, "https://www.rbi.org.in/scripts/x.aspx") == "https://www.rbi.org.in/rdocs/a.PDF"


def test_no_pdf():
    assert find_pdf_url("<p>hello</p><a href='/page.html'>x</a>", BASE) is None


def test_iframe_without_pdf_file_param_is_ignored():
    assert find_pdf_url("<iframe src='/web/?file=notes.txt'></iframe>", BASE) is None


def test_body_length_ignores_script_and_style():
    html = "<html><head><style>p{}</style></head><body><script>var a=1;</script><p>one  two</p></body></html>"
    assert body_text_len(html) == len("one two")
