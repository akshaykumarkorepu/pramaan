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
- PIB RSS: https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3  (Lang=1 returned Hindi; find the English variant)
- User-pasted links allowed only from rbi.org.in, sebi.gov.in, pib.gov.in

## LLM: Groq only
- Use the official `groq` Python SDK (OpenAI-compatible chat completions).
- Model names come from env vars: GROQ_MODEL_PRIMARY (large model for extraction, applicability, Telugu/Hindi),
  GROQ_MODEL_FAST (smaller/faster model for classification and as fallback). Never hardcode model names.
- Use JSON mode / structured output where the chosen model supports it; always validate with Pydantic.
- On invalid JSON: retry once with the validation error included. On 429/5xx: exponential backoff, then fall back
  to GROQ_MODEL_FAST. Never raise raw exceptions to the API layer; return typed errors.
- Temperature 0 for extraction/verification-related calls.
- Log provider, model, tokens and latency per call (shown on the Evidence page later).

## Stack
backend/  Python 3.11, FastAPI, uvicorn, httpx, feedparser, selectolax, pdfplumber, rapidfuzz,
          dateparser, cachetools, groq, gTTS, ics, pydantic, pytest
          Modules: sources/ pipeline/ verify/ llm/ (prompts in llm/prompts/*.md) api/ eval/ scripts/
frontend/ Next.js (App Router, TypeScript), Tailwind, shadcn/ui, lucide-react.
          API client in lib/api.ts. Browser calls the backend directly (not via Next API routes) so SSE streams work.
No database. In-memory TTL cache, 30 min (cachetools). User profile in browser localStorage.
Deploy: backend on Render (Render is connected to Claude Code), frontend on Vercel.

## API contract
GET /health                                   -> {sources:{rbi,sebi,pib:{ok,last_fetch,count}}, llm:{ok,model}}
GET /notices?profile=&lang=                   -> [{id,source,title,url,date,fetched_at,applies:"yes|no|review",reason}]
GET /analyze?url=&profile=&lang=&verifier_test=0|1
     -> text/event-stream. events: {"type":"step","name","status":"running|done|failed","ms","detail"}
        final: {"type":"result","doc":{title,url,fetched_at,paragraphs},
                "obligations":[{who,must_do,deadline,effective_from,paragraph,quote,
                                status:"verified|near|rejected|fixed",reason,match_span,injected_test}],
                "counts":{verified,rejected,fixed},"applies":{value,reason,quote},
                "explainer":{lang,text},"llm":{model,ms}}
GET /tts?text=&lang=                          -> audio/mpeg (fallback voice via gTTS)
GET /ics?url=&profile=                        -> text/calendar of verified deadlines
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
