# Verification record

## Automated checks

- 56 backend tests passed on Python 3.12, including 24 RAG tests.
- Tested PDF (text), DOCX paragraphs/tables, UTF-8 TXT, oversized/invalid uploads, encrypted PDFs and image-only/empty PDF handling.
- Tested baseline scoring, skill boundaries, missing IDs, blank inputs, prompt validation and nonrecursive placeholder replacement.
- Tested custom templates, immutable/concurrent version numbering, unsaved-edit snapshots, same-input comparisons, all-or-nothing comparison persistence, feedback, history across initialization and delete cascades.
- Tested missing Gemini configuration, mocked generateContent success, request headers/model, timeout, quota, credential and server failures, blocked/empty responses, thought-part filtering and truncation; checked error sanitization.
- Checked JavaScript syntax using `node --check`.

## Executed sample

`scripts/export_sample.py` used the actual FastAPI routes in-process (TestClient), uploaded the fictional TXT resume, created its analysis, saved a prompt revision, ran a two-version comparison, and executed the other five templates. Seven prompt runs were generated in a temporary database.

- Detected job skills: 10
- Matched: 7
- Skill coverage: 70%
- Not demonstrated: Redis, Kubernetes, AWS
- Lexical similarity: 53.7%
- Generation: offline deterministic demo; no real provider call

The exported JSON and standalone HTML contain the actual results. `application-output.jpg` is a browser screenshot of that read-only HTML snapshot, not a claim of a working hosted backend.

## Verification limits

The available browser preview host has no usable installation of this Python application's runtime dependencies. Full interactive browser-to-backend testing was therefore not completed. The output snapshot was opened and visually inspected in the browser. The application's API behavior was exercised directly by the automated tests and sample export.

No Google Gemini key was available, so live generation remains unverified against a real provider. Mocked tests verify request structure and error handling but cannot establish account access, billing, model availability, or real model output quality.

The installed Starlette TestClient emitted a non-failing HTTPX deprecation warning; all assertions passed. No CI/CD was provisioned. An owner-private hosted JavaScript/D1 edition was subsequently deployed; see the online verification below.

## Online edition verification

- Production publication succeeded at https://resumelab-prassanna-online.iuwcqd2266703mjlm.chatgpt.site. The production browser reached the expected ChatGPT authentication gate; authenticated production interactions were not tested in the agent browser.
- Hosted engine: 18 Node tests passed, TypeScript check passed, and production build succeeded. Gemini requests and provider responses were mocked; no live key was available.
- Managed browser preview: sample analysis, prompt execution, immutable version saving, comparison, feedback and history persisted through a page reload. PDF and DOCX uploads extracted the expected fictional resume text.
- Hosted code uses JavaScript and D1 because this hosting runtime does not execute the Python backend. It retains owner-private access and does not add public multi-tenant access.
- Publication version: appgprj_6ae6f682baa881918205b16861dfe5f3~appgver_d9f80f3069e8819187dae3d37aa3e3db. Hosted source commit: 6f276ea5390c0b1f5150b62ad4628528fe5a4626.

## RAG update verification (Python repository)

The 56-test suite passed after the RAG implementation. New tests exercise document indexing/retrieval/run/comparison/history as a full API workflow with mocked provider calls; PDF page provenance and DOCX table extraction; normalized batch embeddings and malformed/nonfinite-vector rejection; missing credentials, timeouts and HTTP failures; duplicate/concurrent indexing; collection isolation and model mismatch; empty results; atomic writes/comparison failure; source snapshots and deletion; and an upgrade from a pre-RAG database with preserved output and feedback.

`node --check app/static/app.js` passed. The updated Python UI was not exercised in a browser in this environment. Provider calls remain mocked because no Gemini API key was supplied; real embedding quality, model entitlement and generated answer quality remain unverified. The existing online JavaScript/D1 edition was not changed by this Python RAG update.
