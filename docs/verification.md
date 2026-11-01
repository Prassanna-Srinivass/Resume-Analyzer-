# Verification record

## Automated checks

- 32 backend tests passed on Python 3.12.
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

The installed Starlette TestClient emitted a non-failing HTTPX deprecation warning; all assertions passed. No CI/CD or production hosting was provisioned.
