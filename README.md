# Resume Analyzer with Prompt Engineering

**ResumeLab** is a runnable Python/FastAPI application that compares a resume with a job description, then lets you edit, version, run, compare, and evaluate evidence-based analysis prompts.

Built from the supplied **Resume_Analyser_Prompt_Engineering_Updated_README.md** and **Resume_Analyser_Prompt_Engineering_Project_Guide.pdf**. The target repository was empty at inspection: there was no existing analyzer, frontend, database, LLM service, or RAG implementation to preserve. This project supplies the minimum analyzer foundation and the requested prompt module. The project now also includes optional Gemini embedding retrieval (RAG) over each analysis’s uploaded evidence. It does not implement ChromaDB, model training, automated hiring decisions, Docker, or CI/CD.

[Open the online application](https://resumelab-prassanna-online.iuwcqd2266703mjlm.chatgpt.site) — private to the site owner; sign in with the owning ChatGPT account. Click **Try a sample** to verify the working workflow without an API key.

The hosted edition preserves this interface and workflows using a JavaScript Worker and durable D1 storage; the Python/FastAPI source in this repository remains the local/server edition. Hosted live mode uses the same Gemini model and needs `GEMINI_API_KEY` in Sites runtime secrets. Local `.env` changes do not configure the hosted app.

[Open the read-only sample output](docs/sample-output.html)

The screenshot is a **read-only rendering of actual backend output** using fictional sample inputs in offline demo mode. It is not a screenshot of a live Google Gemini response. The complete export is in [docs/sample-output.html](docs/sample-output.html); download it and open it in a browser. [Raw sample results](docs/sample-output.json) and [verification details](docs/verification.md) are included.

## What works

- Upload **PDF, DOCX, or UTF-8 TXT** resumes (5 MB limit), or paste resume text.
- Add a target role and job description; review detected skills, matching evidence, missing keywords, and lexical similarity.
- Six reusable templates: **Resume Summary, Skill Extractor, Job Skill Matcher, Match Explanation, Resume Improver, Interview Questions**.
- Edit prompts with five validated placeholders; preview the exact populated prompt.
- Create custom templates and save **immutable, numbered versions** with change notes.
- Run saved versions or unsaved edits. Every run records the exact template and rendered prompt, model, settings, output, mode, analysis reference, and timestamp.
- Compare two versions of one template using the **same saved inputs and model settings**.
- Rate relevance, accuracy, coverage, and clarity (1–5), and add feedback.
- Reopen history, reuse prompts, export analysis/runs as JSON, and delete an analysis with its associated runs.
- Switch between a **clearly labelled offline demo** and server-side **Google Gemini live generation**.
- Optional **RAG**: index the saved resume and PDF/DOCX/TXT supporting documents, retrieve relevant passages, inspect source references, and preserve exact evidence snapshots with prompt comparisons.

## Quick start on Windows

Install Python **3.10 or later** (tested on Python 3.12). Download this repository as a ZIP and extract it, or clone it:

```powershell
git clone https://github.com/Prassanna-Srinivass/Resume-Analyzer-.git
cd Resume-Analyzer-
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If you downloaded a ZIP, open PowerShell **inside the extracted folder containing `requirements.txt`**, then start from `py -m venv .venv`. Directly invoking the virtual environment's Python avoids PowerShell activation-policy problems. You do not need Node.js to run the application.

Open **http://127.0.0.1:8000**. Click **Try a sample**, then **Open prompt studio**. Offline mode works immediately without an API key.

Optional virtual-environment activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

If activation is blocked, use the explicit Python commands above; no system policy change is required.

## macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Enable Gemini 3.5 Flash-Lite

Create **`.env` in the project root**, alongside `requirements.txt` and `.env.example`:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
DATABASE_PATH=data/resume_analyzer.db
```

Restart the server, then select **Live AI · Google Gemini** in the upper-right Generation menu. The default model uses the Gemini `generateContent` REST API with `maxOutputTokens=4096`. Deprecated sampling parameters are omitted, so the model uses its defaults. If changing the model, use a compatible text-generation model available to your Google API project. Model availability is controlled by your provider account.

- Credentials stay in the backend. `.env`, databases, uploads, and virtual environments are excluded from Git.
- Live mode sends resume/job content and the prompt to Google Gemini. Each run can incur API charges; comparison sends two requests.
- Missing credentials, rejected credentials, rate limits, network problems, and timeouts produce clear errors. **Live failures never silently return demo output.**
- No real provider call was performed during delivery because no API key was available. Provider success/failure behavior was tested with mocked HTTP responses.
- Offline generation is deterministic and **does not interpret edited instructions**. Use it to explore the workflow, not to judge prompt quality. Identical demo outputs between versions are expected.

## Walkthrough

1. Click **Try a sample**, or upload your resume and paste a job description.
2. Click **Analyze resume**. Review skill coverage and supporting excerpts.
3. Open **Prompt studio**, choose **Job Skill Matcher**, and preview the filled prompt.
4. Run the prompt. The output is saved automatically.
5. Add an instruction such as `Use concise bullets and quote evidence for every match.` and a version note; click **Save new version**.
6. Select two saved versions under **Compare prompt versions** and run the comparison. Switch to Live AI to observe instruction-sensitive generation.
7. Rate an output across all four criteria and save feedback.
8. Open **Analysis history** to restore inputs, inspect exact prompts/results, reuse a prompt, export JSON, or delete saved data.

Editing resume/job inputs creates a new analysis on the next run, preserving earlier run provenance. The `PUT` prompt endpoint also creates a new version instead of mutating old history.

## Use RAG (optional)

RAG augments the full saved resume with relevant passages from **that analysis’s** supporting documents. It does not change the dictionary skill-coverage score. The only external service is Gemini: the same `GEMINI_API_KEY` needs access to both the generation and embedding models. Internet access and adequate API quota are required. No extra Python packages, vector-database account, or LangChain installation are needed.

1. Update your code, install `requirements.txt`, and add `GEMINI_EMBEDDING_MODEL=gemini-embedding-001` to your existing `.env`. Keep your actual key out of Git.
2. Restart the server. Existing SQLite data is upgraded automatically; back up your database before updating.
3. Analyze a resume and job description, then open **Prompt studio → Supporting evidence**.
4. Click **Index saved resume**, or upload a portfolio/project report using **Upload and index a supporting document**. Add only documents belonging to the current candidate. Indexing sends extracted text to Gemini for embeddings.
5. Enter an optional evidence question, choose 3, 5 or 8 passages, and click **Preview retrieved evidence**. Query embedding is a provider call. Inspect the passages rather than treating similarity as factual confidence.
6. Check **Use RAG for this run**, select **Live AI · Google Gemini**, and run a prompt. Evidence is appended automatically to existing templates. Optionally place `{{retrieved_context}}` in an edited prompt.
7. Compare versions: one retrieval snapshot is shared by both generations. Source IDs and citation warnings appear with the output; exact passages persist in history and JSON exports.

The evidence question controls retrieval; the Instructions field still controls the output task. Preview and Run retrieve separately and may differ if documents/settings change between them. Each comparison retrieves once internally.

Use direct mode for short resumes without supporting documents. RAG is **not available for rule-based demo generation** and never silently falls back. [Full RAG setup, architecture, limitations, and Data Analyst walkthrough](docs/rag-guide.md).

## How matching works

The baseline intentionally stays small and inspectable:

- Skills are found with a curated dictionary, aliases, and word boundaries; it is not exhaustive.
- **Skill coverage** = matched detected job skills / all detected job skills. If none are detected, coverage is N/A.
- **Lexical similarity** is cosine similarity of bag-of-words counts. It is not semantic similarity or an ATS prediction.
- Evidence is a short exact excerpt containing the skill. Detection does not verify proficiency, understand all negation, or assess seniority.
- Partial matches require live-model or human interpretation; offline reports explicitly mark them unassessed.
- Missing evidence does not establish a lack of ability. Outputs support human review, not candidate rejection or hiring decisions.

The fictional sample produces **70% skill coverage** (7/10): Python, SQL, FastAPI, PostgreSQL, Git, Docker, REST API. Redis, Kubernetes, and AWS are not demonstrated. Lexical similarity is **53.7%**.

## Project layout

```text
app/
  main.py             FastAPI routes, validation, comparisons, feedback
  analysis.py         File extraction, skill dictionary and lexical baseline
  prompts.py          Six seed templates and safe placeholder replacement
  llm.py              Google Gemini adapter and explicit offline demo
  db.py               SQLite schema, migrations, transactions and seed records
  rag.py              Chunking, Gemini embeddings, cosine retrieval and citations
  static/             HTML, CSS, JavaScript application
examples/             Fictional resume and job description
scripts/
  export_sample.py    Reproducible API-driven output export
  preview.mjs         Optional Node preview launcher; not needed for normal use
tests/                Automated API, parsing, persistence and LLM adapter tests
docs/                 Architecture, verification and actual sample output
.env.example          Backend configuration template
requirements.txt      Runtime dependencies
requirements-dev.txt  Runtime + test dependencies
```

## API

Interactive API documentation: **http://127.0.0.1:8000/docs**. Machine-readable schema: `/openapi.json`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Status, model name and live configuration flag (never the key) |
| POST | `/api/upload` | Extract resume text from multipart `file` |
| GET / POST | `/api/analysis` | List analyses / save new analysis |
| GET / DELETE | `/api/analysis/{id}` | Restore / delete analysis and associated runs |
| GET / POST | `/api/prompts` | List / create templates |
| GET / PUT | `/api/prompts/{id}` | Get versions / save a new version |
| POST | `/api/prompts/{id}/versions` | Save an immutable revision |
| POST | `/api/analysis/{id}/preview` | Populate and validate prompt variables |
| POST | `/api/analysis/{id}/run-prompt` | Run saved or edited prompt |
| POST | `/api/analysis/{id}/compare` | Run two saved versions against identical inputs |
| GET | `/api/analysis/{id}/prompt-runs` | Retrieve run history |
| POST | `/api/prompt-runs/{id}/feedback` | Save manual ratings and a note |

Required placeholder: `{{resume_text}}`. Optional placeholders: `{{job_description}}`, `{{extracted_skills}}`, `{{target_role}}`, `{{retrieved_context}}`. Unknown or malformed placeholders, empty prompts, oversized inputs, unsupported files and invalid ratings are rejected. Substitution is one pass: braces in a resume are not treated as template code.

## Tests and reproducible output

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/export_sample.py
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`. The export uses a temporary database and fictional data, then writes `docs/sample-output.json` and `docs/sample-output.html`. It never calls an external model.

## Storage and deployment limits

SQLite defaults to `data/resume_analyzer.db`, relative to the working directory. Start the app from the repository root. Back up that file if you need to retain history; uploaded binaries are not retained, but extracted text, filled prompts and generated output are stored until deleted.

This is a **single-user local application**, with no login or tenant isolation, as requested by the project plan. Bind to `127.0.0.1` for local use. Before exposing it publicly, add authentication, per-user data separation, upload/request limits at the web server, HTTPS, and appropriate retention controls. GitHub stores the source; it does not automatically host this Python backend. No public deployment was created.

Password-protected, image-only/scanned, unreadable, oversized PDFs, and legacy `.doc` files are not supported. OCR, multi-provider generation, automated citation entailment checking, and batch candidate ranking are not implemented. RAG uses an exact cosine scan over a bounded local collection; it is not a large-scale vector search service.

Model and REST references: [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [generateContent API](https://ai.google.dev/api/generate-content).
