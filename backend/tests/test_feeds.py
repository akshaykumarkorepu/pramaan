from datetime import date

from sources.feeds import FeedItem, is_sebi_circular, newest, parse_feed

RBI = b"""<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>x</title>
<item><title><![CDATA[Update of Sanctions List]]></title><description><![CDATA[<p>body</p>]]></description>
<link>https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=1&amp;Mode=0</link>
<pubDate>Fri, 30 Oct 2026 15:15:00</pubDate></item></channel></rss>"""

SEBI = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Circular A</title><link>https://www.sebi.gov.in/legal/circulars/oct-2026/a_1.html</link><pubDate>30 Oct, 2026 10:00:00 +0530</pubDate></item>
<item><title>Order B</title><link>https://www.sebi.gov.in/enforcement/orders/oct-2026/b_2.html</link><pubDate>30 Oct, 2026 10:00:00 +0530</pubDate></item>
<item><title>Recovery C</title><link>https://www.sebi.gov.in/enforcement/recovery-proceedings/oct-2026/c_3.html</link></item>
<item><title>Press D</title><link>https://www.sebi.gov.in/media-and-notifications/press-releases/oct-2026/d_4.html</link></item>
</channel></rss>"""

PIB = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Scheme news</title><link>https://pib.gov.in/PressReleaseIframePage.aspx?PRID=1</link></item></channel></rss>"""


def test_rbi_item_fields():
    (item,) = parse_feed("rbi", RBI)
    assert item.title == "Update of Sanctions List"
    assert item.url == "https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=1&Mode=0"
    assert item.date == date(2026, 10, 30)
    assert "body" in item.summary


def test_sebi_keeps_only_circulars():
    items = parse_feed("sebi", SEBI)
    assert [i.title for i in items] == ["Circular A"]


def test_sebi_comma_date_parses():
    assert parse_feed("sebi", SEBI)[0].date == date(2026, 10, 30)


def test_non_sebi_sources_are_not_filtered():
    assert len(parse_feed("rbi", SEBI)) == 4


def test_pib_has_no_date():
    (item,) = parse_feed("pib", PIB)
    assert item.date is None


def test_is_sebi_circular():
    assert is_sebi_circular("https://www.sebi.gov.in/legal/circulars/oct-2026/a.html")
    assert not is_sebi_circular("https://www.sebi.gov.in/enforcement/orders/oct-2026/a.html")


def test_newest_by_date():
    a = FeedItem("rbi", "old", "u1", date(2026, 10, 1))
    b = FeedItem("rbi", "new", "u2", date(2026, 10, 30))
    assert newest([a, b]).title == "new"


def test_newest_undated_keeps_feed_order():
    a = FeedItem("pib", "first", "u1", None)
    b = FeedItem("pib", "second", "u2", None)
    assert newest([a, b]).title == "first"


def test_newest_empty():
    assert newest([]) is None


def test_garbage_and_empty_input_give_empty_list():
    assert parse_feed("rbi", b"<html>not a feed") == []
    assert parse_feed("rbi", b"") == []


def test_newest_n_orders_by_date_and_keeps_feed_order_for_ties_and_undated():
    from sources.feeds import newest_n

    items = [
        FeedItem("rbi", "old", "u1", date(2026, 10, 1)),
        FeedItem("rbi", "new-a", "u2", date(2026, 10, 30)),
        FeedItem("rbi", "new-b", "u3", date(2026, 10, 30)),
        FeedItem("rbi", "mid", "u4", date(2026, 10, 15)),
    ]
    assert [i.title for i in newest_n(items, 3)] == ["new-a", "new-b", "mid"]
    undated = [FeedItem("pib", f"p{i}", f"u{i}", None) for i in range(5)]
    assert [i.title for i in newest_n(undated, 2)] == ["p0", "p1"]
    assert newest_n([], 3) == []
