# Pramaan — Forge '26 (Theme 1: Civic Pulse)
Agent that fetches live RBI / SEBI / PIB notices, extracts obligations with verbatim quotes,
verifies every quote/date/number in code, checks applicability to a user profile,
and explains verified items in Telugu/Hindi/English with voice.
Tagline: "New rules, explained in your language, every line proved."

## HARD RULES — breaking these disqualifies the team
- NO dummy data. Never hardcode circulars, sample JSON, mock API responses, placeholder numbers,
  or any "demo mode". All data is fetched live at request time. Unit tests may use short inline strings only.
- No code copied from other projects. Open-source libraries are fine.
- Every obligation the LLM produces must carry a verbatim quote. verify/ rejects anything whose
  quote, dates or numbers are not found in the source text. Rejected items are shown, never hidden.
- The Telugu/Hindi explainer is generated ONLY from verified items, never from raw document text.
- Never put API keys in code or commits. Keys live in .env (local) and Render/Vercel env vars.

## Sources (live)
- RBI notifications RSS: https://www.rbi.org.in/notifications_rss.xml
- SEBI RSS: https://www.sebi.gov.in/sebirss.xml  (keep only links containing /legal/circulars/)
- PIB RSS (English): https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3
  Without `&reg=3`, PIB 302-redirects every Lang value to the Hindi feed. Items have no dates.
- User-pasted links allowed only from rbi.org.in, sebi.gov.in, pib.gov.in
- Allowed hosts are exact: rbi.org.in, rbidocs.rbi.org.in, sebi.gov.in, pib.gov.in (+www.). Redirects are checked too.
- Gotchas (probed 31 Oct): RBI feed items carry the full circular HTML in <description>. SEBI circular pages are a
  thin shell whose body is an iframe to a PDF (`.../web/?file=<pdf url>`), so the PDF fallback is mandatory.
  SEBI pubDate looks like `30 Oct, 2026` (stray comma) so parse with dateparser.

## LLM: Groq only
- Use the official `groq` Python SDK (OpenAI-compatible chat completions).
- Model names come from env vars: GROQ_MODEL_PRIMARY (large model for extraction, applicability, Telugu/Hindi),
  GROQ_MODEL_FAST (smaller/faster model for classification and as fallback). Never hardcode model names.
- Use JSON mode / structured output where the chosen model supports it; always validate with Pydantic.
- On invalid JSON: retry once with the validation error included. On 429/5xx: exponential backoff, then fall back
  to GROQ_MODEL_FAST. Never raise raw exceptions to the API layer; return typed errors.
- Temperature 0 for extraction/verification-related calls.
- Log provider, model, tokens and latency per call (shown on the Evidence page later).
- ALL Groq calls go through llm/client.py (`call_json`, `call_text`); nothing else imports groq. Transient failures
  (429/5xx/timeout): primary -> 1s -> primary -> FAST -> 2s -> FAST. Invalid JSON: one retry with the error included.
  Errors are `LLMError(kind=rate_limit|invalid_output|unavailable|config)` with user-readable messages. Max 4 requests
  in flight. Strict JSON schemas come from `strict_schema(model)` (raw Pydantic schemas get HTTP 400 from Groq).
- Groq free tier = 8,000 tokens/min PER MODEL (checked 31 Oct). The client honours retry-after up to 30 s. Never fire
  several documents' LLM calls concurrently in scripts or tests; run them one at a time.
- verify/ is pure code: it must never import groq, httpx or llm (a test enforces it). A quote is verified only if it is in
  the source AND every number/date in must_do/deadline/effective_from is in the matched text, compared by value.
- Prompts live in llm/prompts/*.md. The RULES in extract.md are the user's wording; do not edit them (a test pins them).
- Load `.env` with python-dotenv (backend/config.py). Never print or log the key.

## Stack
backend/  Python 3.11, FastAPI, uvicorn, httpx, feedparser, selectolax, pdfplumber, rapidfuzz,
          dateparser, cachetools, groq, gTTS, ics, pydantic, pytest
          Modules: sources/ pipeline/ verify/ llm/ (prompts in llm/prompts/*.md) api/ eval/ scripts/
frontend/ Next.js (App Router, TypeScript), Tailwind, shadcn/ui, lucide-react.
          API client in lib/api.ts. Browser calls the backend directly (not via Next API routes) so SSE streams work.
No database. In-memory TTL cache, 30 min (cachetools). User profile in browser localStorage.
Deploy: backend on Render (Render is connected to Claude Code), frontend on Vercel.

## API contract
GET /health                                   -> {sources:{rbi,sebi,pib:{ok,last_fetch,count,error}}, llm:{ok,model,error}, runtime:{ok,error}}
                                                 runtime.ok = pipeline.fetch_document imports (no network); catches a broken pdfplumber install
                                                 source ok = feed has items AND its newest item's page fetched; cached 5 min
GET /notices?profile=&lang=                   -> [{id,source,title,url,date,fetched_at,applies:"yes|no|review",reason}]
GET /analyze?url=&profile=&lang=&verifier_test=0|1
     -> text/event-stream. events: {"type":"step","name","status":"running|done|failed","ms","detail"}
        final: {"type":"result","doc":{title,url,fetched_at,paragraphs:[{id,text}]},
                "obligations":[{who,must_do,deadline,effective_from,paragraph,quote,penalty_or_consequence,
                                status:"verified|near|rejected|fixed",reason,match_span:{start,end,paragraph,para_start,para_end},
                                matched_text,score,paragraph_corrected,injected_test}],
                "counts":{verified,rejected,fixed},"applies":{value,reason,quote},
                "explainer":{lang,text},"llm":{model,ms}}
        or, instead of result on failure: {"type":"error","step","message","url"}  (message is user-readable)
        extraction model (internal) also has optional penalty_or_consequence; not returned by the API
GET /tts?text=&lang=                          -> audio/mpeg (fallback voice via gTTS)
GET /ics?url=&profile=                        -> text/calendar of verified deadlines
Paragraph id = the document's own numbering ("2", "2.1", "3.1(a)"), else "p<index>"; numbering also stays in text.
Profiles: nbfc, coop_bank, research_analyst, stock_broker, citizen_msme
Languages: en, te, hi

## Conventions
- Every external HTTP call: timeout 10s, 2 retries with backoff, browser User-Agent, user-readable error.
  Never return a traceback to the client.
- SSE responses set Cache-Control: no-cache and X-Accel-Buffering: no.
- CORS allows only ALLOWED_ORIGIN.
- Before saying a task is done: backend -> `pytest -q` passes; frontend -> `npm run build` passes.
- Explain non-obvious code with short comments; both teammates must explain all code to judges.
- Feature freeze: Sun 1 Nov, 3:30 PM IST. After that, fixes and docs only.
