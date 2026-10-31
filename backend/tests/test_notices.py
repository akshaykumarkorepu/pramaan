"""/notices with feeds and documents faked (inline strings only). The real rules step runs, so badges are genuine."""
import asyncio
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api import routes_notices
from api.main import app
from pipeline.fetch_document import FetchedDocument
from pipeline.paragraphs import Paragraph
from sources.errors import FetchFailed
from sources.feeds import FeedItem, FeedResult

NOW = datetime(2026, 10, 31, tzinfo=timezone.utc)
TO_COOP = "To All Co-operative Banks. This circular is issued for your information and compliance today."
TO_NBFC = "To All Non-Banking Financial Companies. This circular is issued for your information and compliance today."
UNSURE = "Dear Sir or Madam, kindly note the contents of this notice which are being communicated to you today."


def doc_for(url, text, source="rbi"):
    return FetchedDocument(
        title="t", url=url, source=source, fetched_at=NOW, paragraphs=[Paragraph(id="p0", text=text)],
        full_text=text, char_count=len(text),
    )


class Fakes:
    def __init__(self, monkeypatch):
        self.feeds: dict[str, FeedResult] = {}
        self.texts: dict[str, str] = {}  # url -> document text; missing = fetch fails
        self.fetches = 0
        self.live = 0
        self.max_live = 0
        self.delay = 0.0
        monkeypatch.setattr(routes_notices, "fetch_feed", self.fetch_feed)
        monkeypatch.setattr(routes_notices, "fetch_document", self.fetch_document)

    async def fetch_feed(self, source):
        return self.feeds[source]

    async def fetch_document(self, url):
        self.fetches += 1
        self.live += 1
        self.max_live = max(self.max_live, self.live)
        try:
            await asyncio.sleep(self.delay)
            if url not in self.texts:
                raise FetchFailed("RBI unreachable", url)
            return doc_for(url, self.texts[url], "rbi")
        finally:
            self.live -= 1

    def add(self, source, n, text, day=None, prefix=""):
        items = [
            FeedItem(source, f"{prefix}{source} {i}", f"https://www.{source}.example/{prefix}{source}{i}", date(2026, 10, day or (1 + i)))
            for i in range(n)
        ]
        # pretend the hosts are real: the faked fetch_document never checks them
        for it in items:
            self.texts[it.url] = text
        self.feeds[source] = FeedResult(source, True, items, NOW)
        return items


@pytest.fixture(autouse=True)
def fresh():
    routes_notices.clear_cache()
    yield
    routes_notices.clear_cache()


@pytest.fixture
def fakes(monkeypatch):
    return Fakes(monkeypatch)


@pytest.fixture
def client():
    return TestClient(app)


def get(client, profile="coop_bank", lang="te"):
    r = client.get("/notices", params={"profile": profile, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_sorted_yes_then_review_then_no_newest_first(client, fakes):
    rbi = fakes.add("rbi", 2, TO_COOP)  # yes
    fakes.texts[rbi[0].url] = TO_NBFC  # an NBFC-only notice is "no" for a co-operative bank
    sebi = fakes.add("sebi", 2, UNSURE)  # review
    fakes.feeds["pib"] = FeedResult("pib", True, [FeedItem("pib", "pib 0", "https://pib.example/0", None)], NOW)
    fakes.texts["https://pib.example/0"] = UNSURE
    body = get(client)
    applies = [i["applies"] for i in body["items"]]
    assert applies == sorted(applies, key=["yes", "review", "no"].index)
    assert applies == ["yes", "review", "review", "review", "no"]
    assert body["items"][0]["title"] == "rbi 1" and body["items"][0]["reason"].startswith("Addressed to")
    reviews = body["items"][1:4]
    assert [i["date"] for i in reviews[:2]] == ["2026-10-02", "2026-10-01"]  # newest first among dated
    assert reviews[2]["date"] is None and reviews[2]["reason"] == "Open to check if it applies"  # undated PIB last
    assert set(body["items"][0]) == {"id", "source", "title", "url", "date", "fetched_at", "applies", "reason"}
    assert len(body["items"][0]["id"]) == 12


def test_a_down_source_is_reported_while_the_others_load(client, fakes):
    fakes.add("rbi", 1, TO_COOP)
    fakes.add("sebi", 1, UNSURE)
    fakes.feeds["pib"] = FeedResult("pib", False, error="PIB unreachable, retried 2 times (timeout)")
    body = get(client)
    assert body["sources"]["pib"] == {"ok": False, "error": "PIB unreachable, retried 2 times (timeout)", "count": 0}
    assert body["sources"]["rbi"] == {"ok": True, "error": None, "count": 1}
    assert {i["source"] for i in body["items"]} == {"rbi", "sebi"}


def test_unreadable_document_is_review_not_an_error(client, fakes):
    items = fakes.add("rbi", 2, TO_COOP)
    del fakes.texts[items[0].url]
    fakes.feeds["sebi"] = FeedResult("sebi", True, [], NOW)
    fakes.feeds["pib"] = FeedResult("pib", True, [], NOW)
    body = get(client)
    broken = next(i for i in body["items"] if i["url"] == items[0].url)
    assert broken["applies"] == "review" and broken["reason"] == "Couldn't read it yet — open to try again"


def test_slow_document_times_out_to_review(client, fakes, monkeypatch):
    fakes.add("rbi", 1, TO_COOP)
    fakes.feeds["sebi"] = FeedResult("sebi", True, [], NOW)
    fakes.feeds["pib"] = FeedResult("pib", True, [], NOW)
    fakes.delay = 1.0
    monkeypatch.setattr(routes_notices, "ITEM_TIMEOUT_S", 0.05)
    assert get(client)["items"][0]["reason"] == "Couldn't read it yet — open to try again"


def test_newest_eight_per_source_and_concurrency_limit(client, fakes):
    fakes.add("rbi", 12, TO_COOP)
    fakes.add("sebi", 12, TO_COOP)
    fakes.add("pib", 12, TO_COOP)
    fakes.delay = 0.01
    body = get(client)
    assert len(body["items"]) == 24 and all(s["count"] == 8 for s in body["sources"].values())
    assert fakes.max_live <= 6
    rbi_dates = [i["date"] for i in body["items"] if i["source"] == "rbi"]
    assert rbi_dates == sorted(rbi_dates, reverse=True) and rbi_dates[0] == "2026-10-12"  # the newest 8 of 12


def test_cached_per_profile(client, fakes):
    fakes.add("rbi", 1, TO_COOP)
    fakes.feeds["sebi"] = FeedResult("sebi", True, [], NOW)
    fakes.feeds["pib"] = FeedResult("pib", True, [], NOW)
    get(client)
    get(client, lang="en")  # same profile: served from the 10-minute cache
    assert fakes.fetches == 1
    get(client, profile="nbfc")
    assert fakes.fetches == 2


def test_zero_llm_calls(client, fakes, monkeypatch):
    import llm.client as llm_client

    async def boom(*a, **k):
        raise AssertionError("/notices must not call the LLM")

    monkeypatch.setattr(llm_client, "call_json", boom)
    monkeypatch.setattr(llm_client, "call_text", boom)
    fakes.add("rbi", 2, UNSURE)  # unsure rules would trigger the AI step in /analyze, but never here
    fakes.add("sebi", 1, TO_COOP)
    fakes.feeds["pib"] = FeedResult("pib", True, [], NOW)
    assert len(get(client)["items"]) == 3


def test_bad_profile_or_lang_is_a_friendly_400(client, fakes):
    assert client.get("/notices", params={"profile": "x"}).status_code == 400
    r = client.get("/notices", params={"profile": "nbfc", "lang": "fr"})
    assert r.status_code == 400 and "error" in r.json()


def test_warm_cache_fills_every_profile_without_llm(client, fakes):
    from api.schemas import ProfileId
    from typing import get_args

    fakes.add("rbi", 1, TO_COOP)
    fakes.feeds["sebi"] = FeedResult("sebi", True, [], NOW)
    fakes.feeds["pib"] = FeedResult("pib", True, [], NOW)
    assert asyncio.run(routes_notices.warm_cache()) == len(get_args(ProfileId)) == 5
    fakes.feeds.clear()  # the feeds are gone: only the warmed cache can answer now
    assert get(client, "nbfc")["items"] and get(client, "citizen_msme")["items"]


def test_warm_cache_swallows_failures(fakes, monkeypatch):
    async def boom(profile):
        raise RuntimeError("feeds exploded")

    monkeypatch.setattr(routes_notices, "_build", boom)
    assert asyncio.run(routes_notices.warm_cache()) == 0  # logged, never raised
