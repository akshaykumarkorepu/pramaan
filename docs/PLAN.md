# Pramaan — Build Plan

Team CTRL + AI (NIT Warangal) · Forge '26, Theme 1 · Akshay = backend, Ragula = frontend
Hard deadlines (IST): MVP tag **Sun 1 Nov 2:00 AM** · Feature freeze **Sun 1 Nov 3:30 PM** · Submit **Sun 1 Nov 9:30 PM** (portal closes 11:59 PM) · Live demo **Wed 4 Nov**.

Source of truth for rules and the API contract: [`CLAUDE.md`](../CLAUDE.md). Spec, rubric and demo script: [`Pramaan_Build_and_Demo_Playbook.pdf`](Pramaan_Build_and_Demo_Playbook.pdf). Where the playbook says Gemini or Streamlit, we use **Groq** and **Next.js + FastAPI**.

---

## 1. File tree

### backend/

```
backend/
├── requirements.txt
├── render.yaml                  # (M1) Render blueprint, lives at repo root if Render needs it there
├── pytest.ini
├── api/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, CORS (ALLOWED_ORIGIN), router includes
│   ├── schemas.py               # ALL Pydantic models in section 2 (single source for the contract)
│   ├── routes_health.py         # GET /health, GET /probe (M1, /probe removed or kept as debug in M11)
│   ├── routes_notices.py        # GET /notices
│   ├── routes_analyze.py        # GET /analyze (SSE)
│   ├── routes_media.py          # GET /tts, GET /ics
│   ├── routes_brief.py          # GET /brief (U2)
│   ├── routes_eval.py           # GET /eval (U3)
│   └── sse.py                   # helper: async generator -> text/event-stream with no-cache headers
├── sources/
│   ├── __init__.py
│   ├── http.py                  # shared httpx client: 10 s timeout, 2 retries + backoff, browser UA
│   ├── feeds.py                 # list_notices(source): RBI / SEBI (/legal/circulars/ only) / PIB (English)
│   ├── document.py              # fetch_document(url): HTML -> numbered paragraphs, PDF fallback
│   ├── allowlist.py             # rbi.org.in / sebi.gov.in / pib.gov.in check
│   └── cache.py                 # cachetools.TTLCache(30 min) keyed by URL (+ content hash for analysis)
├── llm/
│   ├── __init__.py
│   ├── client.py                # call_json(prompt, schema, model_role) / call_text(...) via groq SDK
│   ├── errors.py                # LLMError, LLMRateLimited, LLMInvalidOutput (typed, never raw)
│   ├── usage_log.py             # per-call {provider, model, tokens, ms} ring buffer (Evidence page)
│   └── prompts/
│       ├── extract.md           # RULES section written by Akshay
│       ├── re_extract.md
│       ├── applicability.md
│       ├── explain.md
│       └── brief.md             # (U2)
├── pipeline/
│   ├── __init__.py
│   ├── chunk.py                 # split long docs by paragraph into token-bounded chunks
│   ├── extract.py               # extract_obligations(doc) -> list[ExtractedObligation]
│   ├── retry.py                 # re_extract(rejected, doc) — exactly one retry
│   ├── applicability.py         # rules table per profile, LLM only when "unsure"
│   ├── explain.py               # explain(verified, lang) — verified items only
│   ├── ics_export.py            # verified deadlines -> .ics
│   └── run.py                   # orchestrator: async generator yielding StepEvent ... ResultEvent
├── verify/
│   ├── __init__.py
│   ├── normalize.py             # lower, collapse spaces, unify quotes/dashes, Devanagari-safe
│   ├── quotes.py                # exact substring -> rapidfuzz partial_ratio >= 92 sliding window
│   ├── numbers.py               # regex numbers (₹, lakh/crore, %, 1,00,000) + dateparser dates
│   └── verifier.py              # verify(obligations, doc) -> list[Obligation] with status/reason/match_span
├── eval/
│   ├── README.md                # "EVALUATION ONLY — never imported by the app"
│   ├── labels/                  # hand-labelled expectations per circular URL (labels, not source text)
│   └── run.py                   # fetches each URL live, runs pipeline, writes eval/results.json
├── scripts/
│   ├── probe_sources.py         # M1: prints feed counts + first item per source
│   └── groq_smoke.py            # M1: one Telugu completion, prints model + latency
└── tests/
    ├── test_allowlist.py
    ├── test_document_parse.py   # inline HTML snippets only
    ├── test_normalize.py
    ├── test_verifier.py         # exact, near, fake quote, wrong number, wrong date, Hindi
    ├── test_llm_client.py       # retry/fallback with a fake transport (no canned circulars)
    ├── test_applicability_rules.py
    ├── test_sse.py
    └── test_live_smoke.py       # marked @pytest.mark.live — hits real feeds; run with -m live
```

### frontend/

```
frontend/
├── package.json
├── next.config.ts
├── tailwind.config.ts
├── components.json              # shadcn/ui
├── .env.local                   # NEXT_PUBLIC_API_URL (gitignored)
├── app/
│   ├── layout.tsx               # header, "independent tool" footer on every page
│   ├── page.tsx                 # Home: profile + language, Check new rules, notice list, This week brief (U2)
│   ├── circular/page.tsx        # ?url=  -> live analysis view
│   ├── paste/page.tsx           # paste-a-link
│   └── how-it-works/page.tsx    # pipeline diagram, Test the verifier, Evidence (U3)
├── components/
│   ├── ui/                      # shadcn generated
│   ├── ProfilePicker.tsx
│   ├── LanguagePicker.tsx
│   ├── NoticeCard.tsx           # title, source, date, "fetched N min ago", Applies badge
│   ├── StepTimeline.tsx         # live SSE steps with tick + ms
│   ├── VerifierBar.tsx          # "7 verified · 1 rejected · 1 fixed on retry"
│   ├── ObligationCard.tsx       # who/what/by when + highlighted quote; rejected greyed w/ reason
│   ├── ApplicabilityBanner.tsx
│   ├── Explainer.tsx            # text + Play (speechSynthesis te-IN/hi-IN, else /tts audio)
│   ├── SourcePanel.tsx          # (U1) paragraphs, scroll-to + highlight match_span
│   ├── HealthBadge.tsx          # per-source status, "waking server…" on cold start
│   ├── StateViews.tsx           # Loading / Empty / Error blocks
│   └── Footer.tsx
└── lib/
    ├── types.ts                 # mirrors api/schemas.py (section 2)
    ├── api.ts                   # fetch wrappers + analyze() EventSource wrapper
    ├── profile.ts               # localStorage get/set (try/catch)
    └── speech.ts                # voice detection + gTTS fallback
```

---

## 2. Contract types

Rule: `backend/api/schemas.py` and `frontend/lib/types.ts` change together, in the same commit.

### Backend — `api/schemas.py` (Pydantic v2)

```python
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

SourceId = Literal["rbi", "sebi", "pib"]
ProfileId = Literal["nbfc", "coop_bank", "research_analyst", "stock_broker", "citizen_msme"]
Lang = Literal["en", "te", "hi"]
Applies = Literal["yes", "no", "review"]
ObligationStatus = Literal["verified", "near", "rejected", "fixed"]
StepStatus = Literal["running", "done", "failed"]

# ---------- /health ----------
class SourceHealth(BaseModel):
    ok: bool
    last_fetch: Optional[datetime] = None
    count: int = 0
    error: Optional[str] = None            # user-readable, e.g. "RBI unreachable, retried twice"

class LLMHealth(BaseModel):
    ok: bool
    model: Optional[str] = None            # value of GROQ_MODEL_PRIMARY

class HealthResponse(BaseModel):
    sources: dict[SourceId, SourceHealth]
    llm: LLMHealth

# ---------- /notices ----------
class Notice(BaseModel):
    id: str                                # sha1(url)[:12]
    source: SourceId
    title: str
    url: str
    date: Optional[str] = None             # ISO date; PIB feed has none -> null
    fetched_at: datetime
    applies: Applies
    reason: str

# ---------- LLM output (internal, validated before verify) ----------
class ExtractedObligation(BaseModel):
    who: str
    must_do: str
    deadline: Optional[str] = None         # YYYY-MM-DD
    effective_from: Optional[str] = None
    paragraph: Optional[str] = None
    quote: str = ""
    penalty_or_consequence: Optional[str] = None

class ExtractionResult(BaseModel):
    informational: bool = False            # true -> "Informational, no obligations"
    obligations: list[ExtractedObligation] = []

# ---------- /analyze SSE ----------
class Paragraph(BaseModel):
    n: str                                 # "4.2" or running index if unnumbered
    text: str

class Doc(BaseModel):
    title: str
    url: str
    fetched_at: datetime
    paragraphs: list[Paragraph]

class MatchSpan(BaseModel):
    paragraph: str                         # Paragraph.n where the quote was found
    start: int                             # char offsets into that paragraph's ORIGINAL text
    end: int
    matched_text: str                      # shown for "near" matches
    score: float                           # 100.0 exact, >= 92 near

class Obligation(BaseModel):
    who: str
    must_do: str
    deadline: Optional[str] = None
    effective_from: Optional[str] = None
    paragraph: Optional[str] = None
    quote: str
    status: ObligationStatus
    reason: Optional[str] = None           # set when rejected: "quote not found", "number not in source: 10"
    match_span: Optional[MatchSpan] = None
    injected_test: bool = False            # true only for the verifier_test=1 fake claim

class Counts(BaseModel):
    verified: int                          # includes "near"
    rejected: int
    fixed: int

class Applicability(BaseModel):
    value: Applies
    reason: str
    quote: Optional[str] = None            # must itself be verified against the doc

class Explainer(BaseModel):
    lang: Lang
    text: str

class LLMMeta(BaseModel):
    model: str
    ms: int

class StepEvent(BaseModel):
    type: Literal["step"] = "step"
    name: str                              # fetch | read | extract | verify | retry | applicability | explain
    status: StepStatus
    ms: Optional[int] = None
    detail: Optional[str] = None

class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    doc: Doc
    obligations: list[Obligation]
    counts: Counts
    applies: Applicability
    explainer: Optional[Explainer] = None  # null when zero verified items
    llm: LLMMeta

class ErrorEvent(BaseModel):               # proposed addition — terminal, replaces "result"
    type: Literal["error"] = "error"
    step: str
    message: str                           # user-readable; never a traceback
    url: Optional[str] = None              # "read the original" link

# ---------- U2 / U3 ----------
class BriefResponse(BaseModel):
    lang: Lang
    text: str
    notices: list[str]                     # Notice.id list the brief covers
    generated_at: datetime

class EvalResponse(BaseModel):
    run_at: datetime
    circulars: int
    precision: float                       # verified items judged correct / verified items
    recall: float                          # labelled obligations found / labelled obligations
    rejected_rate: float
    avg_latency_ms: int
    avg_tokens: int
    model: str
```

### Frontend — `lib/types.ts`

```ts
export type SourceId = "rbi" | "sebi" | "pib";
export type ProfileId = "nbfc" | "coop_bank" | "research_analyst" | "stock_broker" | "citizen_msme";
export type Lang = "en" | "te" | "hi";
export type Applies = "yes" | "no" | "review";
export type ObligationStatus = "verified" | "near" | "rejected" | "fixed";
export type StepStatus = "running" | "done" | "failed";

export interface SourceHealth { ok: boolean; last_fetch: string | null; count: number; error?: string | null }
export interface HealthResponse { sources: Record<SourceId, SourceHealth>; llm: { ok: boolean; model: string | null } }

export interface Notice {
  id: string; source: SourceId; title: string; url: string;
  date: string | null; fetched_at: string; applies: Applies; reason: string;
}

export interface Paragraph { n: string; text: string }
export interface Doc { title: string; url: string; fetched_at: string; paragraphs: Paragraph[] }
export interface MatchSpan { paragraph: string; start: number; end: number; matched_text: string; score: number }

export interface Obligation {
  who: string; must_do: string; deadline: string | null; effective_from: string | null;
  paragraph: string | null; quote: string; status: ObligationStatus; reason: string | null;
  match_span: MatchSpan | null; injected_test: boolean;
}
export interface Counts { verified: number; rejected: number; fixed: number }
export interface Applicability { value: Applies; reason: string; quote: string | null }
export interface Explainer { lang: Lang; text: string }

export interface StepEvent { type: "step"; name: string; status: StepStatus; ms: number | null; detail: string | null }
export interface ResultEvent {
  type: "result"; doc: Doc; obligations: Obligation[]; counts: Counts;
  applies: Applicability; explainer: Explainer | null; llm: { model: string; ms: number };
}
export interface ErrorEvent { type: "error"; step: string; message: string; url: string | null }
export type AnalyzeEvent = StepEvent | ResultEvent | ErrorEvent;

export interface BriefResponse { lang: Lang; text: string; notices: string[]; generated_at: string }
export interface EvalResponse {
  run_at: string; circulars: number; precision: number; recall: number;
  rejected_rate: number; avg_latency_ms: number; avg_tokens: number; model: string;
}
```

---

## 3. Milestones

Every **DONE WHEN** runs against real, live data. "LIVE_RBI_URL" / "LIVE_SEBI_URL" means *the first item taken from the live feed at test time* (e.g. `python scripts/probe_sources.py --first rbi`), never a pasted constant.

### Backend (Akshay)

| # | Milestone | Files | DONE WHEN |
|---|---|---|---|
| **M1** | **Live data probe + deploy.** Fetch RBI, SEBI, PIB feeds; find English PIB variant; fetch first RBI and first SEBI circular page from the feed (note whether SEBI body is HTML or embedded PDF). Bare FastAPI with `/health` and `/probe`. `render.yaml`. Deploy to Render. One Groq call returning Telugu. | `requirements.txt`, `api/main.py`, `api/routes_health.py`, `sources/http.py`, `scripts/probe_sources.py`, `scripts/groq_smoke.py`, `render.yaml` | `curl $RENDER_URL/probe` shows count > 0 for all 3 feeds **and** HTTP 200 + body length for one RBI and one SEBI circular **fetched from Render**. `python scripts/groq_smoke.py` prints Telugu text + model + ms. Record findings (PIB English URL, SEBI body type) in CLAUDE.md. |
| **M2** | `fetch_document`: HTML → numbered paragraphs, PDF fallback (pdfplumber), domain allow-list, 30-min cache. | `sources/document.py`, `sources/allowlist.py`, `sources/cache.py`, `tests/test_allowlist.py`, `tests/test_document_parse.py` | `pytest -q` green; `pytest -m live -k document` fetches LIVE_RBI_URL and LIVE_SEBI_URL and each returns ≥ 3 paragraphs; a non-gov URL raises a typed refusal. |
| **M3** | `llm/client.py`: Groq SDK, JSON/structured output, Pydantic validation, retry-once-with-error, 429/5xx backoff → `GROQ_MODEL_FAST`, usage log. | `llm/client.py`, `llm/errors.py`, `llm/usage_log.py`, `tests/test_llm_client.py` | Unit tests cover invalid-JSON retry, 429 → fallback, typed error (via fake transport, no canned circulars). Live: one `call_json` returns a validated object and the usage log has model/tokens/ms. |
| **M4** | Extraction. Prompt `llm/prompts/extract.md` — **RULES section left for Akshay to write**; code wires prompt loading, chunking, merge + dedupe, `informational` flag. Document text is wrapped as data (prompt-injection guard). | `pipeline/extract.py`, `pipeline/chunk.py`, `llm/prompts/extract.md` | `python -m pipeline.extract <LIVE_RBI_URL>` prints ≥ 1 `ExtractedObligation` with non-empty quote, or `informational=true` for a no-duty notice. |
| **M5** | Verifier + thorough tests: normalize, exact, near (≥ 92), number/date check, Hindi/Devanagari. | `verify/*.py`, `tests/test_normalize.py`, `tests/test_verifier.py` | `pytest -q tests/test_verifier.py` green with cases: exact, near, fake quote, wrong number, wrong date, Hindi quote, empty quote, ₹/lakh/crore formats. Live: verify M4 output on LIVE_RBI_URL, print counts. |
| **M6** | One self-correction retry for rejected items, then re-verify; mark recovered items `fixed`. | `pipeline/retry.py`, `llm/prompts/re_extract.md` | Live run on LIVE_RBI_URL with `verifier_test`-style injected bad quote shows the retry step runs exactly once; counts include `fixed` when the model recovers. Unit test proves never > 1 retry. |
| **M7** | Applicability: rules table (addressee keywords per profile) first, LLM only when rules say unsure; LLM's quote must pass the verifier, else `review`. | `pipeline/applicability.py`, `llm/prompts/applicability.md`, `tests/test_applicability_rules.py` | Unit tests on inline addressee strings. Live: run all 5 profiles over LIVE_RBI_URL + LIVE_SEBI_URL; at least one differs by profile; every non-`review` LLM answer has a verified quote. |
| **M8** | Explainer in en/te/hi from verified items only (input is the JSON list, never the doc). | `pipeline/explain.py`, `llm/prompts/explain.md` | Live: te and hi explainers for LIVE_RBI_URL; output script is Telugu/Devanagari; every number in the explainer appears in some verified item (code check). Teammate reads Telugu and signs off. |
| **M9** | `/analyze` SSE: orchestrator yields step events, then result or error; `verifier_test=1` injects one clearly labelled fake claim (`injected_test=true`). | `pipeline/run.py`, `api/routes_analyze.py`, `api/sse.py`, `tests/test_sse.py` | `curl -N "localhost:8000/analyze?url=<LIVE_RBI_URL>&profile=nbfc&lang=te"` streams steps then one result; with `verifier_test=1` the injected item is `rejected`. Headers include `Cache-Control: no-cache`, `X-Accel-Buffering: no`. |
| **M10** | `/notices` (parallel feeds, per-source failure isolated, applicability badge), `/tts` (gTTS), `/ics`. | `api/routes_notices.py`, `api/routes_media.py`, `pipeline/ics_export.py`, `sources/feeds.py` | `curl /notices?profile=research_analyst&lang=en` returns live items from ≥ 2 sources; `curl /tts?text=…&lang=te -o a.mp3` plays; `curl /ics?url=<LIVE_RBI_URL>&profile=nbfc` is valid iCalendar (parsed by `ics`) or an empty calendar with a note if no deadlines. |

### Frontend (Ragula)

| # | Milestone | Files | DONE WHEN |
|---|---|---|---|
| **F1** | Next.js bootstrap (App Router, TS, Tailwind, shadcn, lucide). `lib/types.ts`, `lib/api.ts` incl. EventSource wrapper. Home calls `/health`. "Independent tool, not affiliated with RBI, SEBI or the Government of India" footer. | `app/layout.tsx`, `app/page.tsx`, `lib/*`, `components/Footer.tsx`, `components/HealthBadge.tsx` | `npm run build` green; `npm run dev` against local backend shows live per-source health. |
| **F2** | Home: profile + language (localStorage), Check new rules, notice cards with badges, "fetched N min ago", loading / empty / error states (per source). | `app/page.tsx`, `components/ProfilePicker.tsx`, `LanguagePicker.tsx`, `NoticeCard.tsx`, `StateViews.tsx`, `lib/profile.ts` | `npm run build` green; with backend running, real notices render; killing backend shows the error state, not a crash. |
| **F3** | Circular view: live step timeline, verifier bar, obligation cards with quotes, rejected greyed with reason, applicability banner, explainer + Play (speechSynthesis te-IN/hi-IN else `/tts`), .ics download, **Test the verifier** (labelled as inserting one fake claim). | `app/circular/page.tsx`, `components/StepTimeline.tsx`, `VerifierBar.tsx`, `ObligationCard.tsx`, `ApplicabilityBanner.tsx`, `Explainer.tsx`, `lib/speech.ts` | `npm run build` green; opening a live RBI notice streams steps in real time; Test the verifier shows the fake claim rejected. |
| **F4** | Paste-a-link (allow-list check client side too, polite refusal) + How it works page (pipeline diagram, verifier explanation). | `app/paste/page.tsx`, `app/how-it-works/page.tsx` | `npm run build` green; pasting a live SEBI circular URL runs analysis; pasting `https://example.com` shows the refusal naming the 3 accepted sites. |

### Checkpoints

| # | Checkpoint | DONE WHEN |
|---|---|---|
| **C1** | One live circular end-to-end locally (both halves). | Home → pick profile → open a live notice → steps stream → verified cards + Telugu explainer plays. |
| **C2** | Same on deployed Render + Vercel URLs. Set `ALLOWED_ORIGIN` to the Vercel domain. **Tag `mvp`.** Target **Sun 2:00 AM IST**. | C1 flow works on the public URLs from a phone on mobile data; `/precheck` PASS; `git tag mvp && git push --tags`. |

### Hardening and upgrades

| # | Milestone | Owner | DONE WHEN |
|---|---|---|---|
| **M11** | Edge-case hardening (playbook list): source down → only that source fails; cached copy + "fetched N min ago"; empty feed → paste-a-link prompt; informational notice; no body → PDF → "couldn't read" + link; very long circular chunked; Hindi-only doc; broken JSON; 429; all rejected → honest message; non-gov / garbage / empty input; unclear profile → review + quote; no te-IN voice → gTTS; prompt-injection text treated as data. | Akshay (+ Ragula for UI states) | Each row has a test or a scripted manual check in `docs/EDGE_CASES.md` with result; `/precheck` PASS. |
| **U1** | Source side panel: click a card → original scrolls to highlighted `match_span`. | Ragula | `npm run build` green; clicking any verified card on a live circular highlights its sentence. |
| **U2** | "This week for you": `GET /brief?profile=&lang=` → ~60 s Telugu brief of applicable notices (built from verified items), Play button. | Akshay + Ragula | `curl /brief?profile=nbfc&lang=te` returns Telugu text covering ≥ 1 live notice; Play works in the browser. |
| **U3** | Evidence: `eval/labels/` hand-labelled by us (evaluation only, never imported by the app); `eval/run.py` fetches each URL live and scores; `GET /eval` serves the latest `results.json`; How-it-works shows it live. | Akshay + Ragula | `python eval/run.py` prints precision / recall / latency / tokens over our labelled circulars; `grep -r "eval" backend/pipeline backend/sources backend/verify` returns nothing. |
| **U4** | "What changed" diff for amendment circulars. **Only if ahead at 1:00 PM Sunday.** | Akshay | Live amendment circular shows old vs new clause. |
| **FREEZE** | **Sun 3:30 PM IST.** Fixes and docs only. README (pitch, live link, diagram, sources, setup, verifier, eval, limits, roles), 6-slide deck, 2–3 min video recorded on the live app. **Submit by 9:30 PM.** | Both | Submission confirmation received. |

Suggested timeline (IST): Sat 31 Oct — M1–M5 + F1–F2 in parallel by evening; M6–M10 + F3–F4 overnight; C1 ~midnight; C2 + `mvp` tag 2:00 AM; sleep in shifts; Sun — M11, U1–U3 by 1 PM, freeze 3:30 PM.

---

## 4. Risks and fallbacks

| Risk | Detect | Fallback |
|---|---|---|
| Gov sites block Render's IPs | M1 `/probe` from Render shows timeouts/403 | Deploy same repo to **Railway** (then Fly.io); frontend `NEXT_PUBLIC_API_URL` switch. Decide in M1, not later. |
| Groq rate limits / quota | 429s in usage log; `/health` llm.ok false | Exponential backoff → `GROQ_MODEL_FAST`; 30-min analysis cache keyed by URL + content hash; chunk only when needed; check limits in console before demo. |
| Weak Telugu output | M1 smoke test + M8 teammate review | Prompt fixes (short sentences, glossary of fixed terms like RBI/NBFC kept in English, examples of tone); try the other production/preview model; English fallback with a note. |
| SSE buffered on Render | Steps arrive all at once in M9 deployed test | `X-Accel-Buffering: no`, `Cache-Control: no-cache`, flush a comment line (`: ping`) immediately and every 10 s; no gzip on that route. Last resort: poll a job endpoint. |
| No te-IN / hi-IN browser voice | `speechSynthesis.getVoices()` has none for the lang | `/tts` gTTS mp3; if that fails, text only with a note. Test on the demo laptop. |
| Render free-tier cold start (~30–60 s) | First `/health` slow | Frontend shows "waking server…" with retry; hit `/health` 5 min before demo/video. |
| SEBI body only in embedded PDF | M1 probe | pdfplumber path in M2; follow the iframe/PDF link. |
| PIB feed English variant unknown / no dates | M1 probe | Try `Lang=` values; show "date not in feed"; fetch date from the page if present. |
| Feed empty this week | `/notices` count 0 | Empty state offers paste-a-link; keep 2–3 fresh live links for the demo. |

---

## 5. How we use Claude Code

- **One milestone per session.** Start each with Plan mode, paste the milestone row (files + DONE WHEN), agree the plan, then build.
- **`/clear` between milestones** so context stays small and on-task; CLAUDE.md reloads the rules each time.
- **DONE WHEN is the exit test.** A milestone isn't done until its live check passes; `pytest -q` / `npm run build` must be green.
- **Commit after each green step**, small and often, so history shows the build window.
- **Run `/precheck` before every deploy** and before tagging `mvp`.
- We write the prompt RULES and verifier rules ourselves, read every module Claude writes, and explain each other's parts aloud.
- Keys never go into chat, code or commits; deploy and env-var changes always ask first (`.claude/settings.json`).
