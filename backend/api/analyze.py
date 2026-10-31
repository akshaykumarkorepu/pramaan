"""GET /analyze: runs fetch -> extract -> verify -> retry -> applicability -> explain and streams progress as SSE.

Caching is what keeps this inside Groq's 8,000 tokens/min limit:
  per URL                  fetch + extract + verify + retry   (profile-independent)
  per (URL, profile)       applicability
  per (URL, profile, lang) explainer
A per-URL lock makes simultaneous requests for one URL do the work once; the later ones then hit the caches."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, get_args

from cachetools import TTLCache
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.schemas import (
    Applicability, Counts, Doc, ErrorEvent, Explainer, Lang, LLMMeta, ProfileId, ResultEvent, StepEvent, VerifiedObligation,
)
from llm.client import on_wait_var
from llm.errors import LLMError
from pipeline.applicability import check_applicability
from pipeline.explain import USED, build_template, explain
from pipeline.extract import extract
from pipeline.fetch_document import FetchedDocument, fetch_document
from pipeline.models import ExtractionResult
from pipeline.retry import retry
from sources.allowlist import check_allowed
from sources.errors import DocumentError
from verify.verifier import InjectedObligation, verify

log = logging.getLogger("pramaan.analyze")
router = APIRouter()

PING_INTERVAL_S = 10.0  # SSE comment so proxies don't close a quiet connection during a long step
TOTAL_TIMEOUT_S = 150.0
CACHE_TTL_S = 30 * 60

PROFILE_LABEL = {
    "nbfc": "NBFCs",
    "coop_bank": "Co-operative Banks",
    "research_analyst": "Research Analysts",
    "stock_broker": "Stock Brokers",
    "citizen_msme": "Citizens and MSMEs",
}
LANG_NAME = {"en": "English", "te": "Telugu", "hi": "Hindi"}

# The deliberately false claim of verifier_test=1: neither the quote nor the date exists in any real circular.
TEST_CLAIM = InjectedObligation(
    who="Verifier test entity",
    must_do="Deposit a fictitious amount by a fictitious date",
    deadline="2099-12-31",
    effective_from=None,
    paragraph=None,
    quote="Every entity shall deposit the verifier test amount with the regulator by 31 December 2099.",
    penalty_or_consequence=None,
)


@dataclass
class Stage1:
    """Everything that does not depend on the profile or language."""
    doc: FetchedDocument
    extraction: ExtractionResult
    obligations: list[VerifiedObligation]  # after the retry; rejected items are kept
    details: dict[str, str]  # step name -> detail text, replayed with "(cached)" on a cache hit
    model: str
    llm_ms: int


_stage1: TTLCache = TTLCache(maxsize=64, ttl=CACHE_TTL_S)
_applies: TTLCache = TTLCache(maxsize=256, ttl=CACHE_TTL_S)
_explainers: TTLCache = TTLCache(maxsize=512, ttl=CACHE_TTL_S)
_locks: dict[str, list] = {}  # url -> [asyncio.Lock, users]


def clear_caches() -> None:
    for c in (_stage1, _applies, _explainers):
        c.clear()
    _locks.clear()


class _UrlLock:
    """Refcounted per-URL lock; the dict entry disappears when the last user leaves."""

    def __init__(self, url: str):
        self.url = url

    async def __aenter__(self):
        entry = _locks.setdefault(self.url, [asyncio.Lock(), 0])
        entry[1] += 1
        try:
            await entry[0].acquire()
        except BaseException:
            self._leave(entry)
            raise
        self.entry = entry

    async def __aexit__(self, *exc):
        self.entry[0].release()
        self._leave(self.entry)

    def _leave(self, entry):
        entry[1] -= 1
        if entry[1] == 0:
            _locks.pop(self.url, None)


# ---------------------------------------------------------------- events

def _n(count: int, one: str, many: Optional[str] = None) -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


@dataclass
class _Run:
    """One request's event sink. `current` is the step in progress (used by on_wait and by failures)."""
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    current: Optional[str] = None
    started: float = 0.0
    llm_ms: int = 0

    def put(self, event: StepEvent | ErrorEvent | ResultEvent) -> None:
        self.queue.put_nowait(event.model_dump(mode="json"))

    def begin(self, name: str) -> None:
        self.current, self.started = name, time.perf_counter()
        self.put(StepEvent(name=name, status="running"))

    def end(self, detail: str, *, cached: bool = False) -> None:
        ms = 0 if cached else int((time.perf_counter() - self.started) * 1000)
        self.put(StepEvent(name=self.current or "", status="done", ms=ms, detail=detail + (" (cached)" if cached else "")))
        self.current = None

    def instant(self, name: str, detail: str) -> None:
        self.begin(name)
        self.end(detail, cached=True)

    def waiting(self, seconds: float) -> None:
        self.put(StepEvent(name=self.current or "extract", status="running", detail=f"waiting for AI capacity (~{round(seconds)}s)"))

    def fail(self, message: str, url: Optional[str]) -> None:
        step = self.current or "request"
        ms = int((time.perf_counter() - self.started) * 1000) if self.current else None
        if self.current:
            self.put(StepEvent(name=step, status="failed", ms=ms, detail=message))
        self.put(ErrorEvent(step=step, message=message, url=url))
        self.current = None


def _sse(event: dict[str, Any]) -> str:
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


# ---------------------------------------------------------------- pipeline

def _retry_detail(meta) -> str:
    parts = []
    if meta.fixed:
        parts.append(f"{meta.fixed} fixed")
    if meta.rewritten:
        parts.append(f"{meta.rewritten} summary shortened")
    if meta.dropped:
        parts.append(f"{meta.dropped} dropped as unfixable")
    if parts:
        return ", ".join(parts)
    if meta.note:
        return meta.note
    return "nothing to fix — skipped" if meta.llm_calls == 0 else "nothing changed"


async def _stage1_fresh(run: _Run, url: str) -> Stage1:
    details: dict[str, str] = {}
    llm_ms = 0

    run.begin("fetch_document")
    doc = await fetch_document(url)
    details["fetch_document"] = f"{_n(len(doc.paragraphs), 'paragraph')}, read from {'PDF' if doc.from_pdf else 'page'}"
    run.end(details["fetch_document"])

    run.begin("extract")
    extraction, call = await extract(doc)
    llm_ms += call.latency_ms
    details["extract"] = (
        _n(len(extraction.obligations), "duty", "duties") + " found"
        if extraction.obligations else "informational notice, no duties found"
    )
    run.end(details["extract"])
    return Stage1(doc, extraction, [], details, call.model_used, llm_ms)


def _verify_step(run: _Run, st: Stage1, verifier_test: bool, cached: bool) -> Optional[VerifiedObligation]:
    """Returns the live-checked injected claim when verifier_test is on. Real verify results are computed once per URL."""
    run.begin("verify")
    if not cached:
        checked, counts = verify(st.extraction.obligations, st.doc)
        st.obligations = checked
        ok, bad = counts.verified + counts.near, counts.rejected
        st.details["verify"] = f"{_n(len(checked), 'quote')} checked: {ok} verified, {bad} rejected"
    detail = st.details["verify"]
    injected = None
    if verifier_test:
        injected = verify([TEST_CLAIM], st.doc)[0][0]  # pure code, no LLM, so it is always run live
        detail += f" (cached); test claim {injected.status} live" if cached else f"; test claim {injected.status} live"
        run.end(detail)
    else:
        run.end(detail, cached=cached)
    return injected


async def _retry_step(run: _Run, st: Stage1) -> None:
    run.begin("retry")
    final, _, meta = await retry(st.obligations, st.doc)
    st.obligations = final
    st.llm_ms += meta.latency_ms
    st.details["retry"] = _retry_detail(meta)
    run.end(st.details["retry"])


async def _pipeline(run: _Run, url: str, profile: ProfileId, lang: Lang, verifier_test: bool, want_explainer: bool = True) -> None:
    on_wait_var.set(run.waiting)  # this task and the tasks it spawns report Groq rate-limit waits
    async with _UrlLock(url):
        st = _stage1.get(url)
        cached = st is not None
        request_llm_ms = 0
        if cached:
            run.instant("fetch_document", st.details["fetch_document"])
            run.instant("extract", st.details["extract"])
        else:
            st = await _stage1_fresh(run, url)
            request_llm_ms += st.llm_ms
        before_retry = st.llm_ms

        injected = _verify_step(run, st, verifier_test, cached)
        if cached:
            run.instant("retry", st.details["retry"])
        else:
            await _retry_step(run, st)
            request_llm_ms += st.llm_ms - before_retry
            _stage1[url] = st

        # applicability
        key = (url, profile)
        label = PROFILE_LABEL[profile]
        hit = _applies.get(key)
        if hit:
            applies, detail = hit
            run.instant("applicability", detail)
        else:
            run.begin("applicability")
            applies, meta = await check_applicability(profile, st.doc, st.extraction, st.obligations)
            request_llm_ms += meta.latency_ms
            verb = {"yes": "applies to", "no": "does not apply to", "review": "needs review for"}[applies.value]
            detail = f"{verb} {label} — {applies.reason}"
            run.end(detail)
            if meta.method in ("rule", "llm"):  # not the "AI check unavailable" fallback
                _applies[key] = (applies, detail)

        # explainer: only ever built from verified items. It is never null: with no verified duties explain()
        # returns the plain "no verified duties" template (no LLM), so the voice button always has text.
        usable = [o for o in st.obligations if o.status in USED]
        explainer: Optional[Explainer] = None
        if not want_explainer:  # /ics only needs the obligations: a code-built note, no LLM, not cached
            run.instant("explain", "skipped")
            explainer = Explainer(lang=lang, text=build_template(lang, usable, applies), source="template")
        elif not usable:
            run.begin("explain")
            explainer, _ = await explain(st.doc.title, st.obligations, applies, profile, lang)
            run.end("no verified duties, plain note (no AI)")
        else:
            ekey = (url, profile, lang)
            hit = _explainers.get(ekey)
            if hit:
                explainer = hit
                run.instant("explain", _explain_detail(explainer))
            else:
                run.begin("explain")
                explainer, meta = await explain(st.doc.title, st.obligations, applies, profile, lang)
                request_llm_ms += meta.latency_ms
                run.end(_explain_detail(explainer))
                if explainer.source == "llm":  # a template fallback is retried next time instead of being pinned
                    _explainers[ekey] = explainer

    obligations = list(st.obligations) + ([injected] if injected else [])
    counts = Counts(
        verified=sum(o.status in ("verified", "near") for o in st.obligations),
        rejected=sum(o.status == "rejected" for o in st.obligations),
        fixed=sum(o.status == "fixed" for o in st.obligations),
    )
    run.put(ResultEvent(
        doc=Doc(title=st.doc.title, url=st.doc.url, fetched_at=st.doc.fetched_at, paragraphs=st.doc.paragraphs),
        obligations=obligations,
        counts=counts,
        applies=Applicability(value=applies.value, reason=applies.reason, quote=applies.quote),
        explainer=explainer,
        llm=LLMMeta(model=st.model, ms=request_llm_ms),
    ))


def _explain_detail(e: Explainer) -> str:
    return f"{LANG_NAME[e.lang]} explainer, {_n(len(e.text.split()), 'word')}" + (" (built from the verified items, no AI)" if e.source == "template" else "")


async def _produce(run: _Run, url: str, profile: ProfileId, lang: Lang, verifier_test: bool, want_explainer: bool = True) -> None:
    try:
        await _pipeline(run, url, profile, lang, verifier_test, want_explainer)
    except DocumentError as e:
        run.fail(str(e), e.url or url)
    except LLMError as e:
        run.fail(e.message, url)
    except asyncio.CancelledError:
        raise
    except Exception:  # never show a traceback to the client
        log.exception("analyze failed at step %s for %s", run.current, url)
        run.fail("Something went wrong while analysing this notice. Please try again.", url)
    finally:
        run.queue.put_nowait(None)  # end of stream


async def run_analysis(url: str, profile: ProfileId, lang: Lang = "en") -> ResultEvent | ErrorEvent:
    """Non-streaming run for /ics: same pipeline and caches as /analyze, minus the explainer. Never raises."""
    run = _Run()
    try:
        await asyncio.wait_for(_produce(run, url.strip(), profile, lang, False, want_explainer=False), TOTAL_TIMEOUT_S)
    except asyncio.TimeoutError:
        return ErrorEvent(step="request", message="This is taking too long, probably because the AI service is busy. Please try again in a minute.", url=url)
    final = None
    while not run.queue.empty():
        item = run.queue.get_nowait()
        if item is not None and item["type"] in ("result", "error"):
            final = item
    if final is None:
        return ErrorEvent(step="request", message="Something went wrong while analysing this notice. Please try again.", url=url)
    return (ResultEvent if final["type"] == "result" else ErrorEvent).model_validate(final)


async def _stream(url: str, profile: str, lang: str, verifier_test: bool):
    run = _Run()
    problem = _validate(url, profile, lang)
    if problem:
        run.fail(*problem)
        yield _sse(run.queue.get_nowait())
        return

    loop = asyncio.get_running_loop()
    deadline = loop.time() + TOTAL_TIMEOUT_S
    task = asyncio.create_task(_produce(run, url.strip(), profile, lang, verifier_test))  # type: ignore[arg-type]
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                task.cancel()
                run.fail("This is taking too long, probably because the AI service is busy. Please try again in a minute.", url)
                while not run.queue.empty():
                    item = run.queue.get_nowait()
                    if item is not None:
                        yield _sse(item)
                return
            try:
                item = await asyncio.wait_for(run.queue.get(), min(PING_INTERVAL_S, remaining))
            except asyncio.TimeoutError:
                if deadline - loop.time() > 0:
                    yield ": ping\n\n"
                continue
            if item is None:
                return
            yield _sse(item)
    finally:
        task.cancel()  # client went away or we are done


def _validate(url: str, profile: str, lang: str) -> Optional[tuple[str, Optional[str]]]:
    try:
        check_allowed(url or "")
    except DocumentError as e:
        return str(e), url or None
    if profile not in get_args(ProfileId):
        return "Choose who you are (NBFC, co-operative bank, research analyst, stock broker or citizen/MSME) first.", url
    if lang not in get_args(Lang):
        return "Choose English, Telugu or Hindi.", url
    return None


@router.get("/analyze")
async def analyze(url: str = "", profile: str = "", lang: str = "en", verifier_test: str = "0"):
    return StreamingResponse(
        _stream(url, profile, lang, verifier_test == "1"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
