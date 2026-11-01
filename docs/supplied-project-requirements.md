# Resume Analyzer with Prompt Engineering
## Updated Project Overview and Development Plan

**Project type:** Enhancement of your existing Resume Analyzer
**Focus:** Prompt engineering for resume analysis and job matching
**Existing foundation:** Python, FastAPI/Flask, NLP, semantic similarity, RAG, ChromaDB, and your existing LLM integration
**Frontend/storage:** Keep what your current application already uses
**Out of scope:** Docker and CI/CD

> This is NOT a new Prompt Engineering Playground. Keep your existing Resume Analyzer and add a small Prompt Engineering Module to it. Do not rebuild working features.

## 1. Existing Project

Your existing Resume Analyzer analyzes an uploaded resume against a job description. Its current project foundation includes resume analysis, NLP/semantic similarity, skill matching, LLM-assisted suggestions, and RAG/vector search components where implemented.

Keep the working resume upload, parsing, matching, LLM integration, backend, and frontend. First identify where prompts are currently hard-coded.

## 2. Updated Project Idea

Enhance the existing Resume Analyzer with a **Prompt Engineering Module**. Users can select, view, edit, and compare structured prompts for different resume-analysis tasks. The existing LLM integration processes the selected prompt with the resume and job-description content.

**Problem:** Vague or hard-coded instructions can produce generic or inconsistent analysis. Different tasks need different instructions and output formats.

**Objectives**
- Improve the quality and consistency of resume-analysis instructions.
- Create reusable prompts for specific analysis tasks.
- Fill prompt placeholders with resume and job-description content.
- Compare outputs from different prompt versions.
- Save useful prompts, versions, and analysis history.
- Reuse existing project components wherever possible.

## 3. User Workflow

1. User uploads a resume using the existing upload feature.
2. User enters or selects a job description.
3. Existing code extracts and preprocesses the text.
4. User selects an analysis task: summary, skill extraction, job matching, improvement suggestions, or interview questions.
5. Application loads the matching prompt template.
6. Backend inserts resume/job-description values into the template.
7. Existing LLM service generates the result.
8. UI displays the structured result.
9. User can edit the prompt, rerun it, compare versions, and save feedback.

## 4. Prompt Engineering Features

### 4.1 Reusable Prompt Templates

| Template | Purpose |
|---|---|
| Resume Summary | Summarize only information present in the resume |
| Skill Extractor | Extract and group explicitly stated skills |
| Job Skill Matcher | Compare resume skills with job requirements |
| Match Explanation | Explain matched, partial, and missing evidence |
| Resume Improver | Suggest truthful, role-relevant improvements |
| Interview Questions | Generate questions based on the role and stated experience |

### 4.2 Prompt Editor
- View and edit the selected prompt.
- Preview the final prompt after inserting variables.
- Run the edited prompt through the existing LLM service.
- Save a useful revision as a new prompt version.

### 4.3 Prompt Variables

Use placeholders such as:

```text
{{resume_text}}
{{job_description}}
{{extracted_skills}}
{{target_role}}
```

The backend replaces these placeholders with the relevant data before sending the prompt to the existing LLM integration.

### 4.4 Prompt Version Comparison

Run two prompt versions against the same resume and job description. Display both prompt texts and outputs side by side. Compare relevance, clarity, skill coverage, and usefulness. Keep the model and input the same when possible.

### 4.5 Prompt Evaluation

Start with manual ratings:
- Relevance: 1–5
- Accuracy against the supplied resume: 1–5
- Coverage of job requirements: 1–5
- Clarity/usefulness: 1–5
- Optional feedback note

Check that the output does not invent qualifications, skills, employers, or achievements. Automated LLM evaluation can be a later enhancement and must be labelled as an estimate.

### 4.6 Prompt History

Save the prompt name, task, exact prompt text/version, model name if available, analysis-run reference, generated output or output reference, rating, feedback, and timestamp. Extend existing history storage if it already exists; do not duplicate it unnecessarily.

## 5. Example Prompt Templates

### A. Resume Summary

```text
You are a resume analysis assistant.
Write a concise professional summary using only information
explicitly present in the supplied resume.
Do not invent skills, qualifications, employers, achievements,
or years of experience.

Resume:
{{resume_text}}

Return:
1. Professional profile
2. Main technical skills
3. Relevant experience
4. Notable projects
```

### B. Skill Extraction

```text
You are a technical skill extraction assistant.
Extract skills explicitly mentioned in the resume.
Group them into programming languages, frameworks, databases,
tools, and other relevant skills. Do not infer skills.

Resume:
{{resume_text}}

Return valid JSON with keys:
programming_languages, frameworks, databases, tools, other_skills.
```

### C. Job Skill Matching

```text
You are a resume-to-job-description comparison assistant.
Compare the candidate's stated skills with the job requirements.
Separate clearly matched, partially matched, and not-demonstrated skills.
For each match, cite relevant resume evidence.
Do not treat a missing keyword as proof the candidate lacks the skill.

Resume:
{{resume_text}}

Job description:
{{job_description}}

Return a structured report with explanations.
```

### D. Resume Improvement

```text
You are a resume writing assistant.
Suggest improvements that make the resume clearer and more relevant.
Do not add experience, tools, metrics, or achievements unsupported
by the supplied resume.

Resume:
{{resume_text}}

Target role:
{{target_role}}

Job description:
{{job_description}}

Return priority improvements, suggested wording, and missing evidence.
```

## 6. Simple Architecture — Reuse Existing Components

```text
Existing Frontend
  |-- Resume Upload
  |-- Job Description Input
  |-- Existing Analysis Results
  |-- NEW: Prompt Selector / Editor / Comparison
          |
          | Existing REST API
          v
Existing Backend
  |-- Resume Text Extraction
  |-- Existing NLP / Skill Matching
  |-- NEW: Prompt Template Manager
  |-- NEW: Prompt Variable Replacement
  |-- Existing LLM / RAG Service
  |-- Existing Analysis History
          |
          +---- Existing database/storage
          |
          +---- Existing LLM/model integration
```

Do not add a new database or vector store if the current project already has suitable storage. Add only the minimum prompt-template/version records needed.

## 7. Suggested Data Model

Adapt these entities to the current database; they do not require a new database.

### PromptTemplate
- `id`: unique template identifier
- `name`: template name
- `task_type`: summary, matching, extraction, etc.
- `prompt_text`: template instructions
- `created_at`, `updated_at`

### PromptVersion
- `id`: unique version identifier
- `template_id`: related template
- `version_number`: version sequence
- `prompt_text`: exact prompt used
- `change_note`: what changed
- `created_at`

### PromptEvaluation / AnalysisRun
- `id`: unique run identifier
- `prompt_version_id`: prompt version used
- `analysis_reference`: existing resume-analysis record
- `model_name`: model used, if available
- `output_text` or existing output reference
- ratings, feedback, and timestamp

If the existing application already stores analysis runs, extend that record rather than duplicating it.

## 8. Suggested API Changes

Keep existing resume upload and analysis endpoints. Add only what is needed:

| Method | Suggested endpoint | Purpose |
|---|---|---|
| GET | `/api/prompts` | List prompt templates |
| POST | `/api/prompts` | Create a prompt template |
| GET | `/api/prompts/{id}` | View a prompt |
| PUT | `/api/prompts/{id}` | Update a prompt |
| POST | `/api/prompts/{id}/versions` | Save a new version |
| POST | `/api/analysis/{id}/run-prompt` | Rerun analysis with selected prompt |
| GET | `/api/analysis/{id}/prompt-runs` | View prompt runs |
| POST | `/api/prompt-runs/{id}/feedback` | Save ratings and feedback |

Adjust endpoint names to match your existing API. Do not break working routes.

## 9. Frontend Changes

Do not redesign the entire application. Add a small section to the current UI:
1. Keep the existing Resume Analysis page.
2. Add a Prompt Template selector.
3. Add a Prompt Editor panel.
4. Add a Prompt Preview showing the final populated prompt.
5. Add a Run/Rerun action using the existing backend.
6. Add side-by-side output comparison.
7. Add prompt history and feedback controls.

## 10. Development Plan

### Phase 1 — Understand and Preserve
- Run the current project locally.
- Identify resume upload, parsing, analysis, LLM, and storage modules.
- Record existing API routes and UI flow.
- Find hard-coded LLM prompts.
- Do not rewrite working components.

**Deliverable:** A map of the existing flow and where prompts are created.

### Phase 2 — Separate Prompts from Logic
- Move hard-coded LLM instructions into template files or database records.
- Create templates for summary, extraction, matching, and improvement.
- Add placeholder replacement.
- Keep the existing LLM service.

**Deliverable:** Existing analyzer uses reusable prompt templates.

### Phase 3 — Add Prompt Editing
- Add a prompt selector and editor to the current UI.
- Preview the prompt after variable insertion.
- Send edited prompts to the existing backend.
- Validate required variables.

**Deliverable:** Users can edit and run prompts without changing backend source code.

### Phase 4 — Versioning and Comparison
- Save prompt versions.
- Save or reference output for each run.
- Run two versions using the same input.
- Display outputs side by side.

**Deliverable:** Users can compare prompt changes and results.

### Phase 5 — Evaluation and History
- Add manual ratings and feedback.
- Display previous runs.
- Allow prompt reuse.
- Check for unsupported claims and missing resume evidence.

**Deliverable:** Users can review and improve prompt quality.

### Phase 6 — Test and Document
- Confirm existing resume analysis still works.
- Test prompt variable replacement.
- Test empty/invalid prompts.
- Test LLM errors and timeouts.
- Test version history and comparison.
- Update README and screenshots.

**Deliverable:** Existing Resume Analyzer enhanced with prompt engineering.

## 11. Testing Checklist

- Existing resume upload still works.
- Existing text extraction still works.
- Existing resume/job matching still works.
- Each template receives the correct variables.
- Empty prompt instructions are rejected.
- Prompt can be edited and saved as a new version.
- Two versions can be run against the same input.
- Both outputs display correctly.
- Prompt history can be retrieved.
- LLM errors are handled clearly.
- API keys are not exposed in frontend code or logs.
- Suggestions do not invent qualifications or experience.

Use the testing framework already in the project. If none exists, add a small number of backend tests using pytest. Docker and CI/CD are not required.

## 12. Keep, Add, and Do Not Build

| Keep from existing project | Add to existing project | Not required |
|---|---|---|
| Resume upload and parsing | Prompt template manager | New standalone playground |
| Job description input | Prompt editor and preview | Docker |
| NLP and skill extraction | Prompt version history | CI/CD pipeline |
| Semantic similarity | Output comparison | New model training |
| Existing LLM / RAG integration | Manual evaluation and feedback | New vector DB unless needed |
| Existing frontend/backend | Prompt history view | Complete rewrite |

## 13. Minimum Scope — Build These First

1. Keep the current Resume Analyzer working.
2. Move existing hard-coded prompts into reusable templates.
3. Create four templates: Summary, Skill Extraction, Job Matching, and Resume Improvement.
4. Add a prompt selector and simple editor to the existing UI.
5. Save prompt versions and generated outputs.
6. Add basic side-by-side comparison.

Do not start with authentication, multiple LLM providers, complex automated scoring, or a complete UI redesign.

## 14. Expected Final Outcome

The final application remains your existing Resume Analyzer and Ranking System, enhanced with a Prompt Engineering Module.

A user uploads a resume, supplies a job description, selects an analysis task, chooses or edits a prompt template, and receives an LLM-generated result. The user can save prompt versions, compare outputs, and provide feedback.

This demonstrates prompt engineering, Python backend development, REST API integration, NLP and semantic matching, existing LLM/RAG integration, data storage, input validation, error handling, testing, and maintainable application design.

**Updated project title:** Resume Analyzer with Prompt Engineering

**GitHub description:** Enhancement of an existing AI-powered Resume Analyzer with reusable prompt templates, prompt editing, version comparison, and evaluation to improve resume-to-job matching and personalized feedback.

## 15. Local Development Notes

- Continue using the existing virtual environment and dependency setup.
- Keep the current backend and frontend start commands.
- Store LLM credentials in backend environment variables.
- Do not commit real `.env` files or API keys.
- Update dependencies only when a feature requires them.
- Document new environment variables in `.env.example`.

**Assumption:** This plan expects the existing Resume Analyzer already has working resume parsing and an LLM integration. If a component is not implemented, treat it as a future task rather than claiming it already exists.
