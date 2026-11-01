# Implementation map

The supplied documents describe an enhancement, but the requested repository was empty. No routes, prompts, UI or database existed to preserve. The implementation therefore adds a compact FastAPI analyzer plus the prompt module, without inventing pre-existing NLP/RAG components.

## Data flow

1. `POST /api/upload` validates and extracts text (TXT/PDF/DOCX) without retaining the uploaded binary.
2. `POST /api/analysis` saves immutable inputs and the transparent lexical/skill report.
3. `prompts.py` owns six template seeds; `db.initialize` seeds them once.
4. SQLite stores template identity and immutable versions. A serialized transaction allocates the next version number.
5. The preview/run endpoints replace validated placeholders once, with the saved analysis values.
6. `llm.generate` either runs an explicit deterministic demo or calls OpenAI from the backend. There is no silent mode fallback.
7. A run snapshots the base version ID, exact instructions (including unsaved edits), filled prompt, mode, model/configuration, output and analysis reference.
8. Comparison uses two saved versions of one template, one immutable analysis and one captured model configuration. Both successful outputs are stored in one transaction. If either call fails, neither run is stored; the first provider call can still have incurred a charge.
9. The UI renders output using textContent. Manual feedback attaches to the run. Deleting an analysis cascades to its runs; templates and versions remain reusable.

## Storage

One SQLite database contains `templates`, `versions`, `analyses`, and `runs`. There is no second history store or vector database. Foreign keys and a unique `(template_id, version_number)` constraint protect links/version sequences. Timestamps are UTC; the UI displays browser-local time.

## Frontend

The plain JavaScript UI is served by FastAPI on the same origin. Its views are Resume analysis, Prompt studio and Analysis history. No build tool, framework, CDN or frontend API key is required. The optional Node preview runner is separate from normal Python startup.

## Scope mapping

| Supplied requirement | Implementation |
|---|---|
| Preserve existing analyzer | Repository was empty; minimal analyzer foundation supplied |
| Reusable prompts | Six templates, plus custom-template creation |
| Prompt editor and preview | Editable instructions, validated one-pass substitution |
| Version history | Immutable revisions with notes and timestamps |
| Same-input comparison | Same analysis/model/settings; both prompt texts and outputs shown |
| Manual evaluation | Four 1–5 ratings and feedback note |
| Analysis history | Restore, reuse, export, delete |
| Existing LLM integration | None existed; one OpenAI adapter supplied |
| Existing semantic/RAG components | None existed; explicitly documented future work |
| Docker / CI/CD | Not added |
