---
description: Pre-deploy gate — backend tests, frontend build, live /health on Render. Prints a PASS/FAIL table.
---

Run these checks from the repo root, in order. Do not fix anything; just report.

1. **Backend tests** — `cd backend && pytest -q`.
   - PASS if exit code 0. FAIL otherwise; keep the last 15 lines of output.
   - If `backend/` has no tests yet, mark SKIP with the note "no tests yet".
2. **Frontend build** — only if `frontend/package.json` exists: `cd frontend && npm run build`.
   - PASS if exit code 0. FAIL otherwise; keep the first error.
   - If `frontend/package.json` does not exist, mark SKIP with the note "frontend not created yet".
3. **Deployed backend health** — only if the env var `RENDER_URL` is set:
   `curl -sS --max-time 60 "$RENDER_URL/health"` (60 s allows for a Render cold start).
   - PASS if HTTP 200 and every source in `sources` has `"ok": true` and `llm.ok` is true.
   - FAIL otherwise; name which source or the LLM is failing.
   - If `RENDER_URL` is unset, mark SKIP with the note "RENDER_URL not set".

Then print exactly one markdown table:

| Check | Result | Notes |
|---|---|---|
| backend pytest | PASS / FAIL / SKIP | ... |
| frontend build | PASS / FAIL / SKIP | ... |
| Render /health | PASS / FAIL / SKIP | ... |

End with one line: `PRECHECK: PASS` if nothing FAILED, otherwise `PRECHECK: FAIL — do not deploy`.
Never print the contents of `.env` or any secret.
