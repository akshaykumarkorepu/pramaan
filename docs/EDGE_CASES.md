# Edge cases (M11)

Checked on 31 Oct 2026. "Test" = an automated test in `backend/tests/` (inline strings only). "Live" = run against the real
sources and Groq with a local backend. "Not run in a browser" = the handling is in the frontend code and was reviewed, but
nobody clicked through it yet — **do these by hand before the demo** (last section).

| # | Case | How handled | How verified |
|---|---|---|---|
| 1 | A source is down / times out | `sources/http.py`: 10 s timeout, 2 retries with backoff, readable error. `/notices` and `/health` report that source as `ok:false` with the error and still return the others. | Test: `test_http.py` (retries, timeout), `test_notices.py::test_a_down_source_is_reported_while_the_others_load`, `test_health.py::test_one_source_down_does_not_affect_others`. Live: all three feeds were up on 31 Oct, so a real outage was not seen. |
| 2 | Feed is empty | `/notices` returns `items: []` with every source `ok`, count 0. The home page shows the empty state with "Paste a link instead". | Test: `test_edge_cases.py::test_empty_feeds_give_an_empty_but_valid_list`. UI empty state: `StateViews.tsx` (code only, not run in a browser). |
| 3 | Enforcement order / notice with no duties | The extractor returns `kind: informational`; the page says "informational notice, no duties found" and the explainer is a plain note (no AI). | Test: `test_extract.py::test_informational_result_is_accepted`, `test_analyze.py::test_explainer_is_never_null_when_nothing_is_verified`. Not seen on a live notice today. |
| 4 | Page is only a shell and the text is in a PDF | `fetch_document` follows the SEBI iframe to the PDF (allowlisted hosts only). If the PDF is unreadable it says so and links the original. | Test: `test_fetch_document.py` (SEBI shell, direct PDF, thin HTML, image-only PDF, unreadable PDF). Live: the SEBI FPI circular ("read from PDF", 25 paragraphs) analysed end to end. |
| 5 | Very long document | `extract.py` splits into chunks with one paragraph of overlap, merges and de-duplicates the duties. | Test: `test_extract.py` (chunking, overlap, merge, oversize paragraph). Live: only 12–25 paragraph documents were run, so no real long circular. |
| 6 | Hindi-only document | The verifier compares numbers by value, including Devanagari digits ("३०" = 30), and rejects invented quotes in Hindi text. | Test: `test_edge_cases.py::test_hindi_only_document_*`. Extraction quality on a real Hindi-only circular was not run. |
| 7 | Groq returns invalid JSON | `llm/client.py`: one retry with the validation error sent back, then the fast model, then a typed `LLMError(invalid_output)` with a readable message. | Test: `test_llm_client.py` (invalid JSON, json_validate_failed, truncated, empty reply). |
| 8 | Groq 429 / wait | Honours `retry-after` up to 30 s, shows "waiting for AI capacity (~Ns)" in the timeline, falls back to the fast model, then `LLMError(rate_limit)`. | Test: `test_llm_client.py` (429, retry-after, on_wait), `test_analyze.py::test_rate_limit_wait_is_shown_as_a_running_step`. Live: seen for real — one explain step waited 31 s, and a live Groq test fell back to the fast model (3 attempts) while two of my runs shared the 8k tokens/min limit. |
| 9 | All obligations rejected | Rejected items are shown with the reason; the banner/explainer say there are no verified duties; no LLM call for the explainer. | Test: `test_edge_cases.py::test_all_obligations_rejected_*`. Live: one SEBI run extracted 3 duties and the verifier rejected all 3 → the page showed the plain Telugu "no verified duties" note. |
| 10 | Non-government URL | Allowlist is exact-host (rbi.org.in, rbidocs.rbi.org.in, sebi.gov.in, pib.gov.in, +www); redirects are checked too. Look-alikes and `user@host` tricks are refused. | Test: `test_allowlist.py`, `test_fetch_document.py::test_redirect_to_other_site_is_blocked`. Live (`/analyze`): `example.com`, `rbi.org.in@evil.com`, `rbi.org.in.evil.com`, `javascript:` all returned one readable error event. |
| 11 | Empty / garbage input | Backend: one error event, no traceback. Frontend: validated before sending; a bare host such as `sebi.gov.in/...` gets `https://` added; text like `rbi.org.in@evil.com` is refused. | Live: empty, "not a url", bad profile → readable error events; `/tts` empty → 400, 1300 chars → 400 JSON. Frontend `links.ts` run through node with 13 inputs (bare hosts, www, sentence with a link, http://, look-alikes, empty). |
| 12 | No Telugu/Hindi browser voice | Telugu and Hindi now always use the backend gTTS MP3 (`/tts`); English uses the browser voice and falls back to MP3. Loading state while it fetches; errors show a toast and the inline message. | Live: `/tts` te → 200 `audio/mpeg` (20 KB). Test: `test_media.py`. The button and toast were not run in a browser. |
| 13 | Prompt injection inside a document | Document text is wrapped in random-marker data blocks for extraction and for the explainer; the verifier is plain code, so words in the document cannot change what it accepts. | Test: `test_extract.py::test_messages_wrap_document_in_random_matching_markers_and_keep_injection_inside`, `test_edge_cases.py::test_prompt_injection_*`, `::test_instruction_like_item_text_cannot_close_the_explainer_data_block`. No live document with injected text. |
| 14 | Render cold start | Home shows "Waking up the server…" and retries; a circular page whose first connection fails now says the server may still be waking up, with Retry. | Code reviewed (`LiveStatus.tsx`, `StateViews.tsx`, `api.ts`). Not tested against a sleeping Render instance. |
| 15 | SSE connection drops mid-stream | Server sends `: ping` every 10 s and stops its work when the client leaves; the client shows "Connection lost" with Retry and no stale events. | Test: `test_analyze.py::test_pings_are_sent_during_a_slow_step`, `::test_overall_timeout_becomes_an_error_event`. Client drop not run in a browser. |
| 16 | Double-clicking buttons | "Test the verifier" is disabled while a run is active; starting a run cancels the previous stream; Listen ignores clicks while loading. | Code reviewed. Not run in a browser. |
| 17 | Switching language mid-stream | `useAnalyze.start()` closes the old EventSource first; `api.ts` now also drops any late frame from a cancelled stream; the server cancels the old task when the client disconnects. | Code reviewed. Not run in a browser. |

## Found and fixed during this pass
- The verifier-test claim could look "rejected" for the wrong reason: a template quote that exists in the document is still
  rejected when its invented deadline is missing. The picker now insists on the reason "quote not found in source".
- Explainer contradicted the banner (SEBI FPI circular, co-operative bank). Opening sentence now follows yes / review / no;
  verified duties are always listed; an answer that says "no verified duties" while duties exist is regenerated once, then
  replaced by the template. Re-checked live on the same circular: "It is not clear whether this applies to you… " plus the duties.
- Live Telugu answer came back in English (the prompt had grown English examples). New code check: a te/hi answer must be at
  least 25 % Telugu/Devanagari letters, else regenerate once, else template.
- The model sometimes left `\"` in plain text; `clean()` now removes it.
- `rbi.org.in@evil.com` pasted as a bare host was cut down to `rbi.org.in`; it is now refused.
- Share image: the image renderer mangles Devanagari ("हिंदी" lost its ि), so the card writes Hindi in Latin letters and Telugu in Telugu script.

## Still to do by hand (before the demo)
1. Open a circular, switch te → hi → en quickly: only the last language should end up on screen.
2. Double-click "Test the verifier" and "Listen"; click Listen in Telugu with the volume on.
3. Stop the backend mid-analysis; confirm "Connection lost" + Retry.
4. After a deploy, hit the Render URL cold (15+ min idle) and watch the "waking up" message.
5. Paste `sebi.gov.in/legal/circulars/...` (no https) into the paste box.
