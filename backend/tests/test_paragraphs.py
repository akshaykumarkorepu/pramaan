from pipeline.paragraphs import assign_ids, split_text


def ids(text):
    return [p.id for p in split_text(text)]


def test_numbering_kept_in_text_and_used_as_id():
    paras = split_text("1. First duty applies today.\n2. Second duty applies later.\n2.1. Detail of the second duty.")
    assert [(p.id, p.text) for p in paras] == [
        ("1", "1. First duty applies today."),
        ("2", "2. Second duty applies later."),
        ("2.1", "2.1. Detail of the second duty."),
    ]


def test_sub_items_get_parent_prefix_and_stay_unique():
    text = "3.1. Para 4 shall be modified:\n(a) first change;\n(b) second change.\n4.2. Another para:\n(a) third change."
    assert ids(text) == ["3.1", "3.1(a)", "3.1(b)", "4.2", "4.2(a)"]


def test_wrapped_lines_are_joined():
    paras = split_text("1. This sentence is wrapped across\nthree lines of the\nPDF text.")
    assert paras[0].text == "1. This sentence is wrapped across three lines of the PDF text."


def test_hyphenated_line_break_joins_without_space():
    paras = split_text("1. Applies to SWAGAT-\nFI investors.")
    assert paras[0].text == "1. Applies to SWAGAT-FI investors."


def test_page_footers_dropped_and_wrap_continues_across_pages():
    paras = split_text("1. The rule continues across\nPage 1 of 3\na page break.\n2. Next rule applies.")
    assert [p.text for p in paras] == ["1. The rule continues across a page break.", "2. Next rule applies."]


def test_number_inside_wrapped_sentence_is_not_a_new_paragraph():
    # "3.5 crore" starts a line but the sentence before it was not finished
    paras = split_text("1. Entities with net worth above\n3.5 crore must comply.\n2. Others are exempt.")
    assert [p.id for p in paras] == ["1", "2"]
    assert "3.5 crore must comply" in paras[0].text


def test_plain_number_without_dot_is_not_numbering():
    paras = split_text("1. Valid for\n10 years in case of FPIs.")
    assert len(paras) == 1


def test_address_list_then_body_restart_at_one():
    text = "To,\n1. Foreign Portfolio Investors\n2. Custodians and Depositories\nSubject: KYC review\n1. Para 5 of the Master Circular says so."
    texts = [p.text for p in split_text(text)]
    assert texts[0] == "To,"
    assert texts[1] == "1. Foreign Portfolio Investors"
    assert texts[2] == "2. Custodians and Depositories"
    assert texts[3] == "Subject: KYC review"
    assert texts[4].startswith("1. Para 5")


def test_items_ending_with_and_still_split():
    paras = split_text("(a) maintain records; and\n(b) report monthly.")
    assert len(paras) == 2


def test_unnumbered_blocks_get_positional_ids_and_duplicates_are_made_unique():
    paras = assign_ids(["Header line", "1. One", "(a) x", "2. Two", "(a) y", "(a) z"])
    assert [p.id for p in paras] == ["p1", "1", "1(a)", "2", "2(a)", "2(a)-2"]


def test_devanagari_text_is_preserved():
    paras = split_text("1. सभी बैंकों को ₹10 लाख तक का दंड लग सकता है।\n2. यह नियम 1 नवंबर से लागू है।")
    assert paras[0].text == "1. सभी बैंकों को ₹10 लाख तक का दंड लग सकता है।"
    assert [p.id for p in paras] == ["1", "2"]


def test_blank_lines_and_empty_input():
    assert split_text("") == []
    assert split_text("\n \n") == []
