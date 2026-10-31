"""Verified deadlines -> an iCalendar file. Only verified / near / fixed obligations with an explicit date become events."""
import hashlib
from datetime import date

from ics import Calendar, Event

from api.schemas import ResultEvent
from pipeline.explain import USED

MAX_NAME_CHARS = 160  # must_do is capped at 25 words by the extraction prompt


def _trim(text: str, n: int = MAX_NAME_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def build_calendar(result: ResultEvent, url: str) -> tuple[str, int]:
    """-> (ics text, number of events). No deadlines gives a valid empty calendar."""
    cal = Calendar()
    for o in result.obligations:
        if o.status not in USED or o.injected_test or not o.deadline:
            continue
        try:
            day = date.fromisoformat(o.deadline)
        except ValueError:
            continue  # the model's deadline is not a clean YYYY-MM-DD, so it is not put on a calendar
        ev = Event(
            name=_trim(o.must_do),
            begin=day,
            description=f"Who: {o.who}\n\nFrom the circular: \"{o.quote}\"\n\nSource: {url}",
            uid=hashlib.sha1(f"{url}\n{o.quote}".encode()).hexdigest()[:20] + "@pramaan",
            url=url,
        )
        ev.make_all_day()
        cal.events.add(ev)
    return cal.serialize(), len(cal.events)
