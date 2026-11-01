# Verification of mandatory resume RAG

Validated on Python 3.12 with 58 passing pytest cases. JavaScript syntax validation and Python compilation also pass. Provider HTTP contracts are exercised using mocked responses; no real Gemini key was available for a paid end-to-end provider run.

Coverage includes automatic indexing with atomic analysis creation; persistence and reuse of identical resume vectors; query-cache reuse after database reinitialization; analysis scoping; exclusion of legacy supporting documents; source-only prompt construction; rejection of RAG=false and demo API requests; legacy autoindex and model refresh; failed-refresh preservation; invalid/corrupt-vector handling; missing-key, timeout and quota responses; citation-ID warnings; file validation; immutable prompt versions; atomic comparison; feedback and history; and cascading deletion.

The historical docs/sample-output files and screenshot predate mandatory RAG and must not be presented as current live-provider results. Run scripts/export_sample.py with a configured Gemini key to produce a new live fictional sample (embedding calls plus seven generation calls; charges may apply).
