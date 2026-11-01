<div align="center">

# Pramaan

**New rules, explained in your language — every line proved.**

[![Live app](https://img.shields.io/badge/Live_app-pramaan--flame.vercel.app-3730A3)](https://pramaan-flame.vercel.app)
[![Demo video](https://img.shields.io/badge/Demo_video-Google_Drive-6D28D9)](https://drive.google.com/drive/folders/1wb3QtAR_4_E0s3zuUZm6pzEy2A_pLsfB)
![Forge '26](https://img.shields.io/badge/Forge_'26-NIT_Warangal-0F172A)
![Theme 1](https://img.shields.io/badge/Theme_1-Civic_Pulse-16A34A)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-F55036)

[Live app](https://pramaan-flame.vercel.app) · [Demo video & deck](https://drive.google.com/drive/folders/1wb3QtAR_4_E0s3zuUZm6pzEy2A_pLsfB) · [Proof stats](https://pramaan-api-7904.onrender.com/stats)

<img src="docs/screenshots/home.png" alt="Pramaan home page" width="100%">

</div>

## Watch it work

<div align="center">
<img src="docs/media/agent-live.gif" alt="The six agent steps streaming in on a circular" width="90%">
</div>

The six agent steps stream in live on a real RBI circular. This notice was pre-analysed, so it finishes fast.

## The problem

- New rules arrive every week as long English legal text, often PDFs.
- Readers cannot tell if a rule applies to them, what to do, or by when.
- AI chatbots can invent duties and deadlines.

**Who is affected:** small NBFCs, co-operative banks, stock brokers, SEBI research analysts, CAs, and citizens who prefer Telugu or Hindi.

**Why it matters:** missed rules mean penalties and lost rights. This is Civic Pulse: accessible, verified public information and easier compliance.

## Our solution

Pramaan reads live RBI, SEBI and PIB notices, tells you which ones apply to you, and explains the duties in Telugu, Hindi or English. Every duty carries the exact sentence it came from.

**The AI reads and writes. Code checks.**

```mermaid
flowchart LR
    A["Pick profile & language"] --> B["Live notices"]
    B --> C["Applies to you"]
    C --> D["Open a notice"]
    D --> E["Agent works live"]
    E --> F["Verified duties + proof"]
    F --> G["Listen in Telugu / Hindi / English"]
```

| Feature | What it does |
|---|---|
| Live notices | Newest RBI, SEBI and PIB items, fetched when you open the app |
| Verified duties with proof | Each duty shows its word-for-word quote from the official text |
| Show in document | Opens the source with the quote highlighted |
| Test the verifier | Inserts a fake duty on purpose and shows it being rejected |
| Regional-language voice | Telugu, Hindi or English explainer with a Listen button |
| Live proof stats | Running totals of what was verified and rejected, at `/stats` |

<table>
<tr>
<td width="50%"><img src="docs/screenshots/notices.png" alt="Notices"><br><sub><b>Notices that apply to you</b></sub></td>
<td width="50%"><img src="docs/screenshots/circular.png" alt="Agent steps"><br><sub><b>Agent steps on a circular</b></sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/source-panel.png" alt="Proof"><br><sub><b>Quote proved in the text</b></sub></td>
<td><img src="docs/screenshots/telugu.png" alt="Telugu explainer"><br><sub><b>Telugu explainer with voice</b></sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/verifier-test.png" alt="Verifier test"><br><sub><b>Fake duty rejected</b></sub></td>
<td><img src="docs/screenshots/stats.png" alt="Proof stats"><br><sub><b>Live proof stats</b></sub></td>
</tr>
</table>

## How the agent works

```mermaid
flowchart TD
    N["Live notice (RBI · SEBI · PIB)"] --> S1["1. Read document (HTML/PDF)<br/>code"]
    S1 --> S2["2. Extract duties + exact quotes<br/>AI · gpt-oss-120b"]
    S2 --> S3["3. Verify quotes, numbers, dates<br/>code · guardrail"]
    S3 --> S4["4. Self-correct once<br/>AI · gpt-oss-20b"]
    S4 --> S5["5. Does it apply to you?<br/>rules first, AI if unsure"]
    S5 --> S6["6. Explain in your language<br/>AI · verified duties only"]
    S6 --> OUT["Streamed live to the app"]
    S3 -.-> X["Not found in official text"]
    X --> R["Rejected (shown, never hidden)"]

    classDef ai fill:#ede9fe,stroke:#7c3aed,color:#2e1065;
    classDef code fill:#dcfce7,stroke:#16a34a,color:#052e16;
    classDef guard fill:#bbf7d0,stroke:#15803d,stroke-width:4px,color:#052e16;
    classDef bad fill:#fee2e2,stroke:#dc2626,color:#450a0a;
    class S2,S4,S6 ai;
    class S1,S5 code;
    class S3 guard;
    class X,R bad;
```

<div align="center">
<img src="docs/media/verifier-test.gif" alt="Test the verifier: a fake duty is rejected" width="90%">
</div>

A fake duty is inserted on purpose — the verifier rejects it live.

| Guardrail | Why it matters |
|---|---|
| Exact quote required | Every duty must carry a word-for-word quote from the notice |
| Code does the checking | Quotes, numbers and dates are compared in plain code, not by AI |
| Rejected items stay visible | Failed items are shown with the reason, never hidden |
| One self-correction only | The AI gets one repair pass, and the result is checked again |
| Verified duties only | The Telugu/Hindi explainer never sees raw document text |
| Live data only | No stored, mock or dummy notices |

Verified means grounded in the official text. It is not proof that every duty was found. Always confirm with the original.

## Technical architecture

```mermaid
flowchart LR
    SRC["Official sources<br/>RBI · SEBI · PIB"] --> API
    subgraph API["FastAPI backend on Render"]
        P["Agent pipeline"]
        C["12 h cache"]
        W["Background pre-analysis"]
    end
    API <--> G["Groq<br/>gpt-oss-120b / 20b"]
    API -->|"live step stream (SSE)"| FE["Next.js app on Vercel"]
    FE --> U["User"]
    API -.-> E["/tts voice · /ics calendar · /stats"]
```

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind, shadcn/ui |
| Backend | Python 3.11, FastAPI, httpx, feedparser, selectolax |
| Models | Groq: openai/gpt-oss-120b (main), openai/gpt-oss-20b (fast and fallback) |
| Verification | rapidfuzz, dateparser, Pydantic |
| PDF reading | pdfplumber |
| Voice | Browser speech (English), gTTS (Telugu, Hindi) |
| Calendar | ics |
| Hosting | Render (backend), Vercel (frontend) |

| Source | What | Website | Link |
|---|---|---|---|
| RBI | Notifications RSS, full circular HTML | [Notifications](https://www.rbi.org.in/Scripts/NotificationUser.aspx) | [feed](https://www.rbi.org.in/notifications_rss.xml) |
| SEBI | Circulars RSS, plus the linked PDFs | [Circulars](https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0) | [feed](https://www.sebi.gov.in/sebirss.xml) |
| PIB | Press releases RSS (English) | [Press releases](https://www.pib.gov.in/allRel.aspx) | [feed](https://www.pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&reg=3) |

Live official data only — no stored, mock or dummy data. Fetch time is always shown. There is no database; results sit in short-lived in-memory caches.

Tests: 431 offline tests run by default, plus 7 live tests that hit the real sources and run separately (`pytest -m live`).

## Demo

- Prototype: https://pramaan-flame.vercel.app
- Demo video & pitch deck: [Google Drive folder](https://drive.google.com/drive/folders/1wb3QtAR_4_E0s3zuUZm6pzEy2A_pLsfB)
- Backend health: https://pramaan-api-7904.onrender.com/health

Free hosting sleeps when idle, so the first load can take up to a minute.

## Run locally

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env      # then set GROQ_API_KEY in ../.env
uvicorn api.main:app --reload
pytest -q
```

Frontend:

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Groq access (never commit it) |
| `GROQ_MODEL_PRIMARY` | Main model for extraction and explaining |
| `GROQ_MODEL_FAST` | Smaller model for repair, classification and fallback |
| `ALLOWED_ORIGIN` | Frontend URL allowed by CORS |
| `NEXT_PUBLIC_API_URL` | Backend URL, used by the frontend |

## Project structure

```
pramaan/
├── backend/
│   ├── sources/      live feeds, host allowlist, HTTP
│   ├── pipeline/     the agent steps
│   ├── verify/       the guardrail, pure code
│   ├── llm/          Groq client and prompts
│   ├── api/          routes and live stream
│   ├── eval/         evaluation scripts
│   └── tests/        offline and live tests
├── frontend/
│   ├── app/          pages
│   ├── components/   notices, timeline, proof UI
│   └── lib/          typed API client
├── docs/             plan, edge cases, screenshots, GIFs
└── render.yaml       backend deploy config
```

## Limits & next steps

Limits:

- A first analysis on the free AI tier can take about 30 s. Cached notices are instant.
- Source documents must be in English.
- Three sources so far: RBI, SEBI, PIB.
- The free server sleeps when idle.

Next:

- GST/CBIC, DGFT and state gazettes
- WhatsApp delivery
- Per-profile alerts
- More Indian languages

## Team

**CTRL + AI** — Akshay Kumar Korepu & Ragula Thirumal, NIT Warangal. Built during Forge '26 (30 Oct – 1 Nov 2026).

---

*Independent tool. Not affiliated with RBI, SEBI or the Government of India.*
