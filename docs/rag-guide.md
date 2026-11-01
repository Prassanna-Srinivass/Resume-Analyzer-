# Resume-only RAG guide

RAG is mandatory. Supply one resume and a job description; the application automatically builds and stores the resume index. Supporting documents are no longer accepted. No external dataset or vector-database account is needed.

## Configuration

Set GEMINI_API_KEY, GEMINI_MODEL=gemini-3.5-flash-lite and GEMINI_EMBEDDING_MODEL=gemini-embedding-001 in the backend .env. Use persistent storage for DATABASE_PATH. Restart after editing configuration. Missing credentials, timeouts and quota errors are visible errors, not triggers for a non-RAG fallback.

## Data Analyst example

Paste a resume stating: “Built Power BI sales dashboards. Used SQL joins to validate monthly sales totals. Cleaned CSV data using Python and pandas.” Paste a job description requiring SQL, Power BI, Python and stakeholder reporting. Analyze the resume to store its embeddings. In Prompt studio, enter “What resume evidence demonstrates SQL validation and dashboard development?” as the evidence question, preview the retrieved passages, then run Job Skill Matcher.

A grounded response can cite the SQL and dashboard passages. It must not invent stakeholder presentations, quantified savings, employers or years of experience. Exact wording and citation IDs depend on the saved resume and live provider response; this example is not a recorded Gemini result. Refine Instructions to request a table of requirement, evidence, source ID and uncertainty, save a new version, then compare versions using identical retrieved evidence.

## Storage and efficiency

Resume passages and normalized vectors persist in SQLite. An unchanged resume/settings fingerprint reuses document embeddings; identical resumes used with a new job reuse vectors while receiving separate scoped records. Query embeddings are cached per analysis and settings. Search still reranks current passages on every request, and generation runs each time. SQLite performs exact cosine search locally; Gemini does not retain an application-managed searchable resume collection or learn the resume through training.

The model receives the retrieved passages rather than a second complete copy of the resume. For a short resume, all passages may fit; for a long resume, omitted passages can cause incomplete answers. Inspect evidence and adjust the question/count. Similarity scores are relevance measures, not candidate suitability or proof of accuracy. No measured cost, latency or accuracy gain is claimed.

## Upgrade and removal

Existing analyses get resume indexes automatically on their next retrieval. Embedding-model changes refresh the resume index; a provider failure blocks that operation without deleting the last good index. Existing supporting documents are excluded from retrieval. Old histories keep their original evidence snapshots. Delete an analysis to erase its stored resume, vectors, cache and runs; this does not delete copies in other analyses, exports or data retained by an external provider.
