# ResumeLab — Resume Analyzer with Prompt Engineering and RAG

ResumeLab is a Python/FastAPI application for comparing a resume with a job description and experimenting with evidence-based prompts. **RAG is required for every saved resume and every new prompt run.** There is no RAG switch, supporting-document upload, or offline-generation option.

## How it works

1. Upload a PDF, DOCX or UTF-8 TXT resume (up to 5 MB), or paste text. Add a job description and optionally a target role.
2. **Analyze resume** splits the resume into overlapping passages, obtains Gemini embeddings and saves the resume, report, passages and vectors in SQLite. If embedding fails, no incomplete analysis is saved.
3. Review the dictionary-based skill coverage, matched excerpts and lexical similarity.
4. Open **Prompt studio**. Relevant resume passages are retrieved automatically before preview, run and comparison. You can adjust the evidence question and passage count; RAG cannot be disabled.
5. Gemini generates from the retrieved passages with source IDs. Review the cited evidence, save prompt revisions, compare two versions, and rate the output.
6. **Analysis history** restores inputs, prompts, outputs, citations and feedback. Export JSON or delete an analysis and its associated stored data.

Supporting documents previously supplied extra portfolio or project evidence. That feature has been removed: the saved resume is now the only candidate evidence used in new runs. Existing historical snapshots remain readable.

## Required services

One **Gemini API key** with access to the generation model and embedding model, internet access, and sufficient quota. No external dataset, supporting file, ChromaDB, Pinecone or LangChain is required. Your resume supplies the knowledge base; the job description supplies requirements.

Embeddings and resume text are stored **in this application's SQLite database**, not in Gemini's memory. Gemini produces embeddings and generates answers; the backend retrieves passages from SQLite. This is retrieval, not training or fine-tuning.

## First-time setup — Windows PowerShell

Install Python 3.10+ (tested on 3.12), then run:

```powershell
git clone https://github.com/Prassanna-Srinivass/Resume-Analyzer-.git
cd Resume-Analyzer-
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Set these values in `.env`, save it, and close the editor:

```dotenv
GEMINI_API_KEY=your_actual_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
DATABASE_PATH=data/resume_analyzer.db
```

Then run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. **Try a sample also requires Gemini access**, because every analysis is indexed. Keep `.env` private; never commit an actual key.

## macOS / Linux

After cloning and entering the repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with the values above, then:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Update an existing installation

Stop the server and back up `data/resume_analyzer.db` (or your configured database). Run `git pull --ff-only`, install `requirements.txt` again, and add `GEMINI_EMBEDDING_MODEL=gemini-embedding-001` to your existing `.env` without replacing your key. Restart with the same uvicorn command. Schema changes are automatic. Older analyses are indexed on their first retrieval; changing the embedding model refreshes their resume index automatically. A failed refresh preserves the prior index and blocks the run.

## Prompt engineering

Six starter tasks cover summary, skill extraction, job matching, match explanation, resume improvement and interview questions. Instructions control the output task and format; the evidence question controls which resume passages are retrieved. Save immutable versions and compare two versions against the same analysis, retrieved evidence, model and settings. Both results are saved together only if both calls succeed.

`{{resume_text}}` is required and now contains **retrieved resume passages with source IDs**. `{{retrieved_context}}` exposes the same passages if you need a second placement; normally use just one to avoid repetition. `{{extracted_skills}}` contains dictionary skills from the selected passages. `{{job_description}}` and `{{target_role}}` provide role context. Unknown variables are rejected and substitutions run once, so braces in resumes do not execute instructions.

The model receives server-side evidence rules: treat input as data, avoid inventions, cite passage IDs and do not make hiring decisions. Source-ID validation checks missing/unknown references; it does not prove that a cited passage supports a claim.

## Efficiency and limits

- Chunks: up to 1,500 characters with 200-character overlap; maximum 80 per resume.
- Embeddings: 768-dimensional normalized vectors; document requests batched in groups of 20.
- Identical resume text/settings reuse persisted vectors, including when a new job creates a separate analysis. Stored records remain scoped to each analysis.
- Query embeddings are cached per analysis and settings (up to 100 distinct questions). Repeated prompts reuse them. Comparisons share one retrieval snapshot.
- Exact cosine search selects up to eight positive-similarity passages (default five). This suits small resume collections, not large-scale search.
- The full resume is not duplicated into the generation prompt. Long resumes can use fewer input tokens, but no cost or accuracy improvement is guaranteed. Retrieval may omit relevant sections; inspect passages or refine the question/count.
- Generation is not cached: each run makes a Gemini generation request; comparison makes two. Indexing and first-time query embeddings also use API quota.

Skill coverage and lexical similarity remain separate local calculations over the full resume. Coverage is matched dictionary skills divided by detected job skills, not an ATS or hiring score. Missing evidence does not prove missing ability.

## Project structure

| File | Responsibility |
|---|---|
| `app/main.py` | FastAPI validation, automatic indexing, runs, comparisons, feedback |
| `app/analysis.py` | PDF/DOCX/TXT extraction and dictionary/lexical baseline |
| `app/rag.py` | Chunking, Gemini embeddings, persistent cache, retrieval and citations |
| `app/llm.py` | Server-side Gemini generation adapter; historical demo utility |
| `app/prompts.py` | Six seed tasks and validated prompt substitution |
| `app/db.py` | SQLite schema, migrations and transaction handling |
| `app/static/` | Browser interface, served by FastAPI |
| `tests/` | Automated tests using controlled provider responses |

[Architecture](docs/architecture.md) · [RAG guide](docs/rag-guide.md) · [Verification](docs/verification.md)

## API and verification

Interactive API documentation is at http://127.0.0.1:8000/docs. `POST /api/analysis` saves and indexes; `/api/analysis/{id}/retrieve` previews evidence; `/preview`, `/run-prompt`, and `/compare` require retrieval. Requests with `rag_enabled:false` or `mode:"demo"` are rejected. The former supporting-upload endpoint returns 410; deleting an individual resume index is blocked. Delete the analysis to remove its data.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests mock provider boundaries and do not need a real key. To generate a **live** fictional sample export with your configured key, run `python scripts/export_sample.py` using your virtual environment. This makes embedding calls and seven generation calls and writes `docs/live-output.json` and `docs/live-output.html`.

The older `docs/sample-output.*` files and screenshot are **historical offline output**, not verification of the mandatory-RAG workflow. The separately hosted JavaScript edition is also an earlier version; this update applies to the Python repository and does not redeploy that site.

## Storage and deployment

SQLite stores resumes, vectors, query caches, exact prompts, outputs and feedback until deletion. Analysis deletion cascades to its records; identical resume copies in other analyses and previously exported files remain. Old supporting-document rows are excluded from retrieval and removed when their analysis is deleted. No uploaded binary is retained. Resume text goes to Gemini for embedding; retrieved passages, job description and instructions go for generation. API errors are reported without silently substituting a demo.

This is a single-user local application. For public hosting, authentication, per-user data separation, HTTPS, request limits and persistent disk storage still need deployment work. GitHub stores source and does not automatically run the backend. Scanned PDFs require OCR outside this app; encrypted PDFs and legacy `.doc` files are rejected.

Provider references: [API key](https://aistudio.google.com/apikey), [embeddings API](https://ai.google.dev/api/embeddings), [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).
