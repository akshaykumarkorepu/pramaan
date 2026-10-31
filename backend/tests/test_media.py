"""/tts and /ics with gTTS and the analysis faked (inline strings only)."""
import pytest
from fastapi.testclient import TestClient
from ics import Calendar

from api import analyze, routes_media
from api.main import app
from api.schemas import Applicability, Counts, Doc, ErrorEvent, Explainer, LLMMeta, ResultEvent, VerifiedObligation
from datetime import datetime, timezone

URL = "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=1"


@pytest.fixture
def client():
    routes_media._audio.clear()
    return TestClient(app)


@pytest.fixture
def synth(monkeypatch):
    calls = []

    def fake(text, lang):
        calls.append((text, lang))
        return b"ID3-fake-mp3"

    monkeypatch.setattr(routes_media, "_synthesize", fake)
    return calls


# ---------------------------------------------------------------- /tts

def test_tts_returns_mp3_and_caches(client, synth):
    r = client.get("/tts", params={"text": "నమస్తే", "lang": "te"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3-fake-mp3"
    client.get("/tts", params={"text": "నమస్తే", "lang": "te"})
    assert synth == [("నమస్తే", "te")]  # second call from the cache
    client.get("/tts", params={"text": "నమస్తే", "lang": "hi"})
    assert len(synth) == 2  # the cache key includes the language


def test_tts_length_limit(client, synth):
    ok = client.get("/tts", params={"text": "a" * 1200, "lang": "en"})
    assert ok.status_code == 200
    r = client.get("/tts", params={"text": "a" * 1201, "lang": "en"})
    assert r.status_code == 400 and "too long" in r.json()["error"] and "1200" in r.json()["error"]


def test_tts_bad_input(client, synth):
    assert client.get("/tts", params={"text": "hi", "lang": "fr"}).status_code == 400
    assert client.get("/tts", params={"text": "  ", "lang": "en"}).status_code == 400
    assert synth == []


def test_tts_failure_is_a_503_with_a_readable_message(client, monkeypatch):
    def boom(text, lang):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(routes_media, "_synthesize", boom)
    r = client.get("/tts", params={"text": "hello", "lang": "en"})
    assert r.status_code == 503 and "secret" not in r.text and "voice" in r.json()["error"].lower()


# ---------------------------------------------------------------- /ics

def ob(status, deadline, quote, injected=False):
    return VerifiedObligation(
        who="Co-operative Banks", must_do="File the return", deadline=deadline, quote=quote, status=status, injected_test=injected,
    )


def result(obligations):
    return ResultEvent(
        doc=Doc(title="t", url=URL, fetched_at=datetime(2026, 10, 31, tzinfo=timezone.utc), paragraphs=[]),
        obligations=obligations, counts=Counts(verified=0, rejected=0, fixed=0),
        applies=Applicability(value="yes", reason="r"), explainer=Explainer(lang="en", text="x"), llm=LLMMeta(model="m", ms=0),
    )


@pytest.fixture
def analysis(monkeypatch):
    box = {}

    async def fake(url, profile, lang="en"):
        return box["result"]

    monkeypatch.setattr(routes_media, "run_analysis", fake)
    return box


def test_ics_only_verified_near_fixed_with_deadlines(client, analysis):
    analysis["result"] = result([
        ob("verified", "2027-01-31", "Banks shall file the return by 31 January 2027."),
        ob("near", "2026-12-15", "Banks shall pay by 15 December 2026."),
        ob("fixed", "2026-11-30", "Banks shall report by 30 November 2026."),
        ob("rejected", "2026-11-01", "Invented duty with a date."),
        ob("verified", None, "A duty with no date at all in this sentence."),
        ob("verified", "soon", "A duty whose date is not ISO at all here."),
        ob("verified", "2099-12-31", "Injected claim must never reach a calendar.", injected=True),
    ])
    r = client.get("/ics", params={"url": URL, "profile": "coop_bank"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar") and r.headers["x-pramaan-events"] == "3"
    assert r.headers["content-disposition"].startswith('attachment; filename="pramaan-rbi-') and r.headers["content-disposition"].endswith('.ics"')
    cal = Calendar(r.text)
    events = sorted(cal.events, key=lambda e: e.begin)
    assert [e.begin.date().isoformat() for e in events] == ["2026-11-30", "2026-12-15", "2027-01-31"]
    assert all(e.all_day for e in events)
    e = events[-1]
    assert e.name == "File the return"
    assert "Co-operative Banks" in e.description and "by 31 January 2027." in e.description and URL in e.description
    assert len({e.uid for e in events}) == 3


def test_ics_no_events_is_a_valid_empty_calendar(client, analysis):
    analysis["result"] = result([ob("rejected", "2026-11-01", "Invented duty with a date.")])
    r = client.get("/ics", params={"url": URL, "profile": "coop_bank"})
    assert r.status_code == 200 and r.headers["x-pramaan-events"] == "0"
    assert r.text.startswith("BEGIN:VCALENDAR") and r.text.strip().endswith("END:VCALENDAR")
    assert len(Calendar(r.text).events) == 0


def test_ics_long_summary_is_trimmed(client, analysis):
    long = ob("verified", "2026-12-01", "Banks shall file the return by 1 December 2026.")
    long.must_do = "word " * 60
    analysis["result"] = result([long])
    ev = next(iter(Calendar(client.get("/ics", params={"url": URL, "profile": "nbfc"}).text).events))
    assert len(ev.name) <= 160 and ev.name.endswith("…")


def test_ics_rejects_bad_input_and_reports_pipeline_errors(client, analysis):
    assert client.get("/ics", params={"url": "https://evil.example/x", "profile": "nbfc"}).status_code == 400
    assert client.get("/ics", params={"url": URL, "profile": "zzz"}).status_code == 400
    analysis["result"] = ErrorEvent(step="fetch_document", message="RBI unreachable.", url=URL)
    r = client.get("/ics", params={"url": URL, "profile": "nbfc"})
    assert r.status_code == 502 and r.json() == {"error": "RBI unreachable."}
