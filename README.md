# Audiobook Generator

Local AI audiobook generator with a **clean architecture** foundation. This repository contains project scaffolding only — business logic (PDF parsing, TTS, job orchestration) is not implemented yet.

## Tech stack

| Layer | Technology |
|-------|------------|
| API | FastAPI |
| UI | HTML, Tailwind CSS (CDN), vanilla JavaScript |
| Database | SQLite (SQLAlchemy) |
| Storage | Local filesystem under `storage/` |

## Project structure

```
AminVoice/
├── backend/           # Python API and clean architecture layers
├── frontend/          # Templates and static assets
├── storage/           # Runtime data (jobs, chunks, outputs, logs)
├── tokens/            # Per-project API config (example only)
├── prototypes/        # Working Gemini TTS scripts (reference core)
├── tests/
├── run.py             # Start server and open dashboard
└── .env.example
```

## Prototype Core

The `prototypes/` folder holds the **working reference implementation** for Gemini TTS. These scripts are not part of the FastAPI app yet; they validate API behavior before migration into clean architecture.

| File | Role |
|------|------|
| `prototypes/ai_studio_code.py` | Original streaming TTS script (`generate_content_stream`) |
| `prototypes/ai_studio_nonstream.py` | **Current working Gemini TTS engine** — uses `generate_content()` (non-streaming) |
| `prototypes/api_limit_test.py` | Batch test harness for free-tier / rate limits |

**`ai_studio_nonstream.py`** is the engine to preserve: it solved the ~20-second audio chunk limitation caused by streaming mode by returning a single complete audio response.

**Planned migration path:** logic from `ai_studio_nonstream.py` will move into:

`backend/infrastructure/tts/gemini_tts_engine.py`

Run prototypes from the project root (requires `GEMINI_API_KEY`):

```bash
python prototypes/ai_studio_nonstream.py
```

## Prerequisites

- Python 3.11+
- pip

## Setup

1. **Clone or open the project** and go to the project root:

   ```bash
   cd AminVoice
   ```

2. **Create a virtual environment** (recommended):

   ```bash
   python -m venv .venv
   ```

   Windows:

   ```bash
   .venv\Scripts\activate
   ```

   macOS / Linux:

   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure environment**:

   ```bash
   copy .env.example .env
   ```

   Edit `.env` as needed. Defaults work for local development.

5. **Run the application**:

   ```bash
   python run.py
   ```

   The server starts at `http://127.0.0.1:8000` and opens the dashboard in your browser.

## Useful URLs

| URL | Description |
|-----|-------------|
| `/dashboard` | Main UI (placeholders) |
| `/health` | API health check |
| `/docs` | OpenAPI docs (FastAPI) |

## PDF extraction benchmark (diagnostic)

Compare extractors on a Persian PDF page:

```bash
python prototypes/pdf_extraction_compare.py
```

Edit `PDF_PATH` and `PAGE_NUMBERS` at the top of that script. Outputs go to `storage/debug/pdf_compare/`.

## Phase 1 — PDF intake

Upload a Persian PDF on the dashboard (`/dashboard`). The app extracts text, applies conservative cleaning, and shows a **page-by-page preview** before generation.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/pdf/upload` | POST | Upload PDF (`multipart/form-data`, field `file`) |
| `/api/v1/pdf/{id}/text` | PUT | Save edited full text |
| `/api/v1/pdf/{id}/continue` | POST | Placeholder — chunking / TTS not implemented |
| `/api/v1/pdf/{id}` | DELETE | Cancel intake session |

Services: `backend/services/pdf_extractor.py` (PyMuPDF), `backend/services/text_cleaner.py`.

## Running tests

```bash
pip install -r backend/requirements.txt
pytest tests/ -v
```

## Architecture overview

Dependencies point **inward**:

```
api → application → domain ← infrastructure
```

- **domain**: entities and repository interfaces (no FastAPI, no SQLAlchemy)
- **application**: use cases and ports (PDF, TTS, chunking) — TODO
- **infrastructure**: SQLite, filesystem, Gemini adapter — TODO
- **api**: HTTP routes, request/response schemas

## Next steps (integration)

1. **PDF parsing** — implement `PDFParserPort` in `application/interfaces`, adapter in `infrastructure`
2. **Gemini TTS** — implement `TTSProviderPort`, read keys from `.env` / `tokens/projects.json`
3. **Job use cases** — `GenerateAudiobookUseCase`, `ResumeJobUseCase` in `application/use_cases`
4. **REST API** — `backend/api/routes/jobs.py` for upload, start, resume, progress
5. **Frontend** — enable controls in `frontend/static/js/app.js`, poll or WebSocket progress
6. **File layout** — write chunks to `storage/chunks/`, outputs to `storage/outputs/`

## License

Private / local use — add your license as needed.
