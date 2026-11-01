import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from . import db, llm, rag
from .analysis import MAX_UPLOAD, analyze, extract_file
from .prompts import TASKS, render_prompt, validate_prompt

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    yield


app = FastAPI(
    title="Resume Analyzer with Prompt Engineering", version="1.0.0", lifespan=lifespan
)


@app.middleware("http")
async def headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        if not request.url.path.startswith("/docs")
        else "default-src 'self' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' https://fastapi.tiangolo.com"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


class AnalysisInput(BaseModel):
    resume_text: str = Field(min_length=1, max_length=50000)
    job_description: str = Field(min_length=1, max_length=20000)
    target_role: str = Field(default="", max_length=200)

    @field_validator("resume_text", "job_description")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value.strip()


class VersionInput(BaseModel):
    prompt_text: str = Field(min_length=1, max_length=20000)
    change_note: str = Field(default="", max_length=500)

    @field_validator("prompt_text")
    @classmethod
    def valid(cls, value):
        validate_prompt(value)
        return value.strip()


class TemplateInput(VersionInput):
    name: str = Field(min_length=1, max_length=100)
    task_type: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()

    @field_validator("task_type")
    @classmethod
    def valid_task(cls, value):
        if value not in TASKS:
            raise ValueError("Select a supported analysis task.")
        return value


class RetrievalOptions(BaseModel):
    rag_enabled: Literal[True] = True
    rag_query: str = Field(default="", max_length=1000)
    top_k: int = Field(default=5, ge=1, le=8, strict=True)


class PreviewInput(VersionInput, RetrievalOptions):
    pass


class RunInput(RetrievalOptions):
    prompt_version_id: int = Field(gt=0)
    prompt_text: str | None = Field(default=None, max_length=20000)
    mode: Literal["live"] = "live"

    @field_validator("prompt_text")
    @classmethod
    def valid_draft(cls, value):
        if value is not None:
            validate_prompt(value)
        return value


class CompareInput(RetrievalOptions):
    version_a: int = Field(gt=0)
    version_b: int = Field(gt=0)
    mode: Literal["live"] = "live"


class FeedbackInput(BaseModel):
    relevance: int = Field(ge=1, le=5, strict=True)
    accuracy: int = Field(ge=1, le=5, strict=True)
    coverage: int = Field(ge=1, le=5, strict=True)
    clarity: int = Field(ge=1, le=5, strict=True)
    note: str = Field(default="", max_length=2000)


def required(row, label):
    if row is None:
        raise HTTPException(404, f"{label} not found.")
    return dict(row)


def get_analysis(aid):
    with db.connect() as conn:
        row = required(
            conn.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone(),
            "Analysis",
        )
    row["report"] = json.loads(row["report"])
    return row


def get_version(vid):
    with db.connect() as conn:
        return required(
            conn.execute(
                "SELECT v.*,t.name,t.task_type FROM versions v JOIN templates t ON t.id=v.template_id WHERE v.id=?",
                (vid,),
            ).fetchone(),
            "Prompt version",
        )


def values_for(analysis):
    return {
        **analysis,
        "extracted_skills": json.dumps(
            analysis["report"]["skills"], ensure_ascii=False
        ),
    }


def decode_run(row):
    item = dict(row)
    item["feedback"] = json.loads(item["feedback"]) if item["feedback"] else None
    item["generation_settings"] = json.loads(item["generation_settings"])
    item["retrieval_snapshot"] = (
        json.loads(item["retrieval_snapshot"])
        if item.get("retrieval_snapshot")
        else None
    )
    return item


def retrieval_for(analysis, request, mode=None):
    try:
        return rag.retrieve(analysis, request.rag_query, request.top_k)
    except llm.LLMError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def prepare_run(analysis, request, config, snapshot=None):
    version = get_version(request.prompt_version_id)
    prompt = (
        version["prompt_text"] if request.prompt_text is None else request.prompt_text
    )
    try:
        rendered = rag.render_with_evidence(
            prompt, analysis, values_for(analysis), snapshot
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        output = llm.generate(
            rendered, version["task_type"], analysis, request.mode, config
        )
    except llm.LLMError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    saved_snapshot = (
        {**snapshot, "citation_check": rag.citation_check(output, snapshot)}
        if snapshot
        else None
    )
    return {
        "retrieval_snapshot": json.dumps(saved_snapshot) if saved_snapshot else None,
        "analysis_id": analysis["id"],
        "prompt_version_id": version["id"],
        "prompt_name": version["name"],
        "task_type": version["task_type"],
        "prompt_text": prompt,
        "rendered_prompt": rendered,
        "model_name": config["model"],
        "mode": request.mode,
        "output_text": output,
        "generation_settings": json.dumps(config),
    }


def save_run(conn, record, comparison_id=None):
    record = {**record, "comparison_id": comparison_id}
    columns = ",".join(record.keys())
    marks = ",".join("?" for _ in record)
    rid = conn.execute(
        f"INSERT INTO runs ({columns}) VALUES ({marks})", tuple(record.values())
    ).lastrowid
    return decode_run(
        conn.execute(
            "SELECT r.*,v.template_id FROM runs r JOIN versions v ON v.id=r.prompt_version_id WHERE r.id=?",
            (rid,),
        ).fetchone()
    )


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "live_available": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "live_model": llm.model_config("live")["model"],
        "rag_required": True,
        "embedding_model": os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"),
    }


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    try:
        data = file.file.read(MAX_UPLOAD + 1)
        return {
            "filename": Path(file.filename or "resume").name,
            "resume_text": extract_file(file.filename, data),
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        file.file.close()


@app.post("/api/analysis", status_code=201)
def create_analysis(body: AnalysisInput):
    try:
        prepared = rag.prepare_resume(body.resume_text)
    except llm.LLMError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    report = analyze(body.resume_text, body.job_description)
    with db.connect() as conn:
        aid = conn.execute(
            "INSERT INTO analyses(resume_text,job_description,target_role,report) VALUES (?,?,?,?)",
            (
                body.resume_text,
                body.job_description,
                body.target_role,
                json.dumps(report),
            ),
        ).lastrowid
        rag.save_resume(conn, aid, prepared)
    return get_analysis(aid)


@app.get("/api/analysis")
def list_analyses():
    with db.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id,target_role,created_at FROM analyses ORDER BY id DESC LIMIT 100"
            )
        ]


@app.get("/api/analysis/{aid}")
def read_analysis(aid: int):
    return get_analysis(aid)


@app.delete("/api/analysis/{aid}", status_code=204)
def delete_analysis(aid: int):
    with db.connect() as conn:
        if not conn.execute("DELETE FROM analyses WHERE id=?", (aid,)).rowcount:
            raise HTTPException(404, "Analysis not found.")


@app.get("/api/prompts")
def list_prompts():
    with db.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT t.*,v.id AS version_id,v.version_number,v.prompt_text FROM templates t JOIN versions v ON t.id=v.template_id WHERE v.version_number=(SELECT MAX(version_number) FROM versions WHERE template_id=t.id) ORDER BY t.id"
            )
        ]


@app.get("/api/prompts/{tid}")
def read_prompt(tid: int):
    with db.connect() as conn:
        prompt = required(
            conn.execute("SELECT * FROM templates WHERE id=?", (tid,)).fetchone(),
            "Prompt",
        )
        prompt["versions"] = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM versions WHERE template_id=? ORDER BY version_number DESC",
                (tid,),
            )
        ]
    return prompt


@app.post("/api/prompts", status_code=201)
def create_prompt(body: TemplateInput):
    with db.connect() as conn:
        tid = conn.execute(
            "INSERT INTO templates(name,task_type) VALUES (?,?)",
            (body.name, body.task_type),
        ).lastrowid
        conn.execute(
            "INSERT INTO versions(template_id,version_number,prompt_text,change_note) VALUES (?,1,?,?)",
            (tid, body.prompt_text, body.change_note),
        )
    return read_prompt(tid)


@app.put("/api/prompts/{tid}")
@app.post("/api/prompts/{tid}/versions", status_code=201)
def save_version(tid: int, body: VersionInput):
    with db.connect() as conn:
        # Serialize MAX+1 and INSERT across workers without mutable version history.
        conn.execute("BEGIN IMMEDIATE")
        required(
            conn.execute("SELECT id FROM templates WHERE id=?", (tid,)).fetchone(),
            "Prompt",
        )
        number = conn.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM versions WHERE template_id=?",
            (tid,),
        ).fetchone()[0]
        vid = conn.execute(
            "INSERT INTO versions(template_id,version_number,prompt_text,change_note) VALUES (?,?,?,?)",
            (tid, number, body.prompt_text, body.change_note),
        ).lastrowid
        conn.execute(
            "UPDATE templates SET updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
            (tid,),
        )
    return get_version(vid)


@app.get("/api/analysis/{aid}/documents")
def list_documents(aid: int):
    get_analysis(aid)
    return rag.documents(aid)


@app.post("/api/analysis/{aid}/documents")
def add_document(aid: int):
    get_analysis(aid)
    raise HTTPException(
        410,
        "Supporting documents have been removed. Only the saved resume is indexed automatically.",
    )


@app.delete("/api/analysis/{aid}/documents/{did}")
def delete_document(aid: int, did: int):
    get_analysis(aid)
    raise HTTPException(
        409,
        "The resume index is required. Delete the analysis to remove its stored data.",
    )


@app.post("/api/analysis/{aid}/retrieve")
def retrieve_evidence(aid: int, body: RetrievalOptions):
    return retrieval_for(get_analysis(aid), body)


@app.post("/api/analysis/{aid}/preview")
def preview(aid: int, body: PreviewInput):
    analysis = get_analysis(aid)
    snapshot = retrieval_for(analysis, body)
    return {
        "rendered_prompt": rag.render_with_evidence(
            body.prompt_text, analysis, values_for(analysis), snapshot
        ),
        "retrieval_snapshot": snapshot,
    }


@app.post("/api/analysis/{aid}/run-prompt", status_code=201)
def run_prompt(aid: int, body: RunInput):
    analysis = get_analysis(aid)
    get_version(body.prompt_version_id)  # Validate before any billable retrieval.
    snapshot = retrieval_for(analysis, body, body.mode)
    config = llm.model_config(body.mode)
    if snapshot:
        config["rag_enabled"] = True
    record = prepare_run(analysis, body, config, snapshot)
    with db.connect() as conn:
        return save_run(conn, record)


@app.post("/api/analysis/{aid}/compare", status_code=201)
def compare(aid: int, body: CompareInput):
    if body.version_a == body.version_b:
        raise HTTPException(422, "Select two different saved versions.")
    va, vb = get_version(body.version_a), get_version(body.version_b)
    if va["template_id"] != vb["template_id"]:
        raise HTTPException(422, "Compare versions of the same prompt template.")
    analysis, config = get_analysis(aid), llm.model_config(body.mode)
    snapshot = retrieval_for(analysis, body, body.mode)
    if snapshot:
        config["rag_enabled"] = True
    # Retrieve once: both prompts receive exactly the same evidence snapshot.
    # Same immutable inputs/model/settings; persist the pair atomically.
    records = [
        prepare_run(
            analysis, RunInput(prompt_version_id=v, mode=body.mode), config, snapshot
        )
        for v in [body.version_a, body.version_b]
    ]
    cid = str(uuid.uuid4())
    with db.connect() as conn:
        runs = [save_run(conn, record, cid) for record in records]
    return {"comparison_id": cid, "runs": runs}


@app.get("/api/analysis/{aid}/prompt-runs")
def list_runs(aid: int):
    get_analysis(aid)
    with db.connect() as conn:
        return [
            decode_run(row)
            for row in conn.execute(
                "SELECT r.*,v.template_id FROM runs r JOIN versions v ON v.id=r.prompt_version_id WHERE r.analysis_id=? ORDER BY r.id DESC",
                (aid,),
            )
        ]


@app.post("/api/prompt-runs/{rid}/feedback")
def feedback(rid: int, body: FeedbackInput):
    with db.connect() as conn:
        if not conn.execute(
            "UPDATE runs SET feedback=? WHERE id=?",
            (json.dumps(body.model_dump()), rid),
        ).rowcount:
            raise HTTPException(404, "Prompt run not found.")
        return decode_run(
            conn.execute(
                "SELECT r.*,v.template_id FROM runs r JOIN versions v ON v.id=r.prompt_version_id WHERE r.id=?",
                (rid,),
            ).fetchone()
        )


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
