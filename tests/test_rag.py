import json
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from app import db, rag, llm
from app.analysis import extract_sections
from app.main import get_analysis


def make_analysis(client, text="Python analyst with SQL and Power BI."):
    return client.post(
        "/api/analysis",
        json={
            "resume_text": text,
            "job_description": "SQL data validation and sales dashboards",
            "target_role": "Data Analyst",
        },
    ).json()


def vector(axis=0):
    result = [0.0] * rag.DIMENSIONS
    result[axis] = 1.0
    return result


@pytest.fixture
def fake_embeddings(monkeypatch):
    calls = []

    def fake(texts, task, config):
        calls.append((texts, task, config))
        return [
            vector(
                0
                if any(w in text.lower() for w in ["sql", "validation", "dashboard"])
                else 1
            )
            for text in texts
        ]

    monkeypatch.setattr(rag, "embed", fake)
    return calls


def test_auto_index_cache_restart_scope_and_cascade(client, fake_embeddings):
    a = make_analysis(client)
    aid = a["id"]
    assert len(rag.documents(aid)) == 1
    assert len(fake_embeddings) == 1
    b = make_analysis(client)  # identical resume reuses vectors, separate scope
    assert len(fake_embeddings) == 1
    assert rag.documents(aid)[0]["id"] != rag.documents(b["id"])[0]["id"]
    first = client.post(f"/api/analysis/{aid}/retrieve", json={}).json()
    assert len(first["sources"]) == 1 and not first["query_cached"]
    db.initialize()
    again = client.post(f"/api/analysis/{aid}/retrieve", json={}).json()
    assert again["query_cached"] and again["sources"] == first["sources"]
    assert len(fake_embeddings) == 2
    client.delete(f"/api/analysis/{aid}")
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM rag_queries WHERE analysis_id=?", (aid,)
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM rag_documents WHERE analysis_id=?", (aid,)
            ).fetchone()[0]
            == 0
        )
    assert rag.documents(b["id"])


def test_mandatory_rag_and_removed_supporting_documents(client, fake_embeddings):
    aid = make_analysis(client)["id"]
    for endpoint, body in [
        ("run-prompt", {"prompt_version_id": 1, "rag_enabled": False}),
        ("run-prompt", {"prompt_version_id": 1, "mode": "demo"}),
        ("preview", {"prompt_text": "{{resume_text}}", "rag_enabled": False}),
        ("retrieve", {"rag_enabled": False}),
    ]:
        assert (
            client.post(f"/api/analysis/{aid}/{endpoint}", json=body).status_code == 422
        )
    assert (
        client.post(
            f"/api/analysis/{aid}/documents",
            files={"file": ("extra.txt", b"SQL secret")},
        ).status_code
        == 410
    )
    assert client.delete(f"/api/analysis/{aid}/documents/1").status_code == 409
    for k in [0, 9, True]:
        assert (
            client.post(f"/api/analysis/{aid}/retrieve", json={"top_k": k}).status_code
            == 422
        )
    shell = client.get("/").text
    for control in [
        'id="rag-file"',
        'id="rag-enabled"',
        'id="index-resume"',
        'id="mode"',
    ]:
        assert control not in shell


def test_index_failure_rolls_back_analysis(client, monkeypatch):
    def fail(*args):
        raise llm.LLMError("Embedding unavailable", 503)

    monkeypatch.setattr(rag, "embed", fail)
    response = client.post(
        "/api/analysis", json={"resume_text": "SQL", "job_description": "SQL"}
    )
    assert response.status_code == 503
    with db.connect() as conn:
        for table in ["analyses", "rag_documents", "rag_chunks"]:
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_missing_key_real_embedding_boundary(client, monkeypatch):
    # Restore the actual provider function rather than relying on the fixture stub.
    import importlib

    real = importlib.reload(rag).embed
    monkeypatch.setattr(rag, "embed", real)
    response = client.post(
        "/api/analysis", json={"resume_text": "SQL", "job_description": "SQL"}
    )
    assert response.status_code == 503 and "GEMINI_API_KEY" in response.text


def test_legacy_autoindex_and_model_refresh(client, fake_embeddings, monkeypatch):
    a = make_analysis(client)
    with db.connect() as conn:
        conn.execute("DELETE FROM rag_documents")
    assert client.post(f"/api/analysis/{a['id']}/retrieve", json={}).status_code == 200
    old_id = rag.documents(a["id"])[0]["id"]
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-new")
    assert client.post(f"/api/analysis/{a['id']}/retrieve", json={}).status_code == 200
    assert len(rag.documents(a["id"])) == 1
    assert rag.documents(a["id"])[0]["id"] != old_id
    assert rag.documents(a["id"])[0]["embedding_model"] == "gemini-embedding-new"


def test_old_supporting_docs_excluded(client, fake_embeddings):
    a = make_analysis(client)
    with db.connect() as conn:
        did = conn.execute(
            "INSERT INTO rag_documents(analysis_id,filename,kind,fingerprint,embedding_model,dimensions,chunk_count) VALUES (?,'extra','supporting','legacy','gemini-embedding-001',768,1)",
            (a["id"],),
        ).lastrowid
        conn.execute(
            "INSERT INTO rag_chunks(document_id,position,text,embedding) VALUES (?,1,?,?)",
            (did, "SECRET SUPPORT", json.dumps(vector())),
        )
    result = client.post(f"/api/analysis/{a['id']}/retrieve", json={}).json()
    assert "SECRET SUPPORT" not in json.dumps(result)
    assert len(rag.documents(a["id"])) == 1


def test_compare_retrieves_once_and_saves_snapshot(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)
    version = client.post(
        "/api/prompts/1/versions", json={"prompt_text": "Three bullets {{resume_text}}"}
    ).json()
    prompts = []

    def generate(prompt, task, analysis, mode, config):
        assert config["rag_enabled"] and mode == "live"
        prompts.append(prompt)
        return "SQL documented [D1-C1]."

    monkeypatch.setattr(llm, "generate", generate)
    response = client.post(
        f"/api/analysis/{a['id']}/compare",
        json={"version_a": 1, "version_b": version["id"]},
    )
    assert response.status_code == 201
    runs = response.json()["runs"]
    assert (
        len(fake_embeddings) == 2
    )  # one document call and one query for BOTH versions
    assert runs[0]["retrieval_snapshot"] == runs[1]["retrieval_snapshot"]
    assert len(prompts) == 2 and prompts[0] != prompts[1]
    assert runs[0]["retrieval_snapshot"]["citation_check"]["warnings"] == []


def test_only_selected_passages_in_prompt(client, monkeypatch):
    text = "SQL project. " * 150 + "NEVER_RETRIEVED_SECRET " * 100

    def embed(texts, task, config):
        return [
            vector(0 if task == "RETRIEVAL_QUERY" or "NEVER_RETRIEVED" not in t else 1)
            for t in texts
        ]

    monkeypatch.setattr(rag, "embed", embed)
    a = make_analysis(client, text)
    result = client.post(
        f"/api/analysis/{a['id']}/preview",
        json={"prompt_text": "{{resume_text}} {{extracted_skills}}", "top_k": 1},
    ).json()
    assert "NEVER_RETRIEVED_SECRET" not in result["rendered_prompt"]
    assert "D1-C1" in result["rendered_prompt"]
    assert "SQL" in result["rendered_prompt"]
    assert rag.citation_check("bad [D999-C1]", result["retrieval_snapshot"])["warnings"]


def test_chunk_overlap_and_concurrent_resume_ensure(client, fake_embeddings):
    chunks = rag.chunk_sections([{"text": "A" * 4000, "page": 1}])
    assert sum(len(c["text"]) for c in chunks) == 4000 + rag.OVERLAP * (len(chunks) - 1)
    a = make_analysis(client)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: rag.ensure_resume(a), range(3)))
    assert len(rag.documents(a["id"])) == 1


def test_gemini_embedding_contract_normalization_batching(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = []

    def post(self, url, **kwargs):
        assert url.endswith("/models/gemini-embedding-001:batchEmbedContents")
        assert "test-key" not in url
        assert kwargs["headers"]["x-goog-api-key"] == "test-key"
        requests = kwargs["json"]["requests"]
        calls.append(requests)
        assert requests[0]["embedContentConfig"] == {
            "taskType": "RETRIEVAL_DOCUMENT",
            "outputDimensionality": 768,
        }
        assert requests[0]["model"] == "models/gemini-embedding-001"
        raw = [3.0, 4.0] + [0.0] * 766
        return httpx.Response(
            200, json={"embeddings": [{"values": raw} for _ in requests]}
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    vectors = rag.embed(["text"] * 21, "RETRIEVAL_DOCUMENT", rag.settings())
    assert [len(c) for c in calls] == [20, 1]
    assert vectors[0][:2] == [0.6, 0.8]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"embeddings": []},
        {"embeddings": [{"values": [1]}]},
        {"embeddings": [{"values": [0] * 768}]},
        {"embeddings": [{"values": ["secret"] * 768}]},
    ],
)
def test_embedding_invalid_response(monkeypatch, body):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        httpx.Client, "post", lambda *a, **k: httpx.Response(200, json=body)
    )
    with pytest.raises(llm.LLMError, match="invalid embeddings"):
        rag.embed(["text"], "RETRIEVAL_QUERY", rag.settings())


@pytest.mark.parametrize(
    "code,status", [(429, 429), (403, 502), (404, 502), (500, 502)]
)
def test_embedding_http_failure(monkeypatch, code, status):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **k: httpx.Response(code, text="provider secret details"),
    )
    with pytest.raises(llm.LLMError) as error:
        rag.embed(["text"], "RETRIEVAL_QUERY", rag.settings())
    assert error.value.status == status and "secret details" not in str(error.value)


def test_system_guard_requires_resume_passages(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def post(self, url, **kwargs):
        text = kwargs["json"]["systemInstruction"]["parts"][0]["text"]
        assert text == rag.RAG_GUARD
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Documented [D1-C1]"}]},
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    assert (
        llm.generate(
            "p",
            "summary",
            {},
            "live",
            {**llm.model_config("live"), "rag_enabled": True},
        )
        == "Documented [D1-C1]"
    )


def test_upgrade_legacy_database_preserves_history(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "legacy.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    # A pre-RAG database with a real run and feedback but no new tables/column.
    schema = """CREATE TABLE templates(id INTEGER PRIMARY KEY,name TEXT NOT NULL,task_type TEXT NOT NULL,created_at TEXT,updated_at TEXT);
    CREATE TABLE versions(id INTEGER PRIMARY KEY,template_id INTEGER NOT NULL REFERENCES templates(id),version_number INTEGER,prompt_text TEXT,change_note TEXT,created_at TEXT,UNIQUE(template_id,version_number));
    CREATE TABLE analyses(id INTEGER PRIMARY KEY,resume_text TEXT,job_description TEXT,target_role TEXT,report TEXT,created_at TEXT);
    CREATE TABLE runs(id INTEGER PRIMARY KEY,analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,prompt_version_id INTEGER NOT NULL REFERENCES versions(id),prompt_name TEXT,task_type TEXT,prompt_text TEXT,rendered_prompt TEXT,model_name TEXT,mode TEXT,output_text TEXT,feedback TEXT,comparison_id TEXT,generation_settings TEXT,created_at TEXT);
    INSERT INTO templates VALUES(1,'Existing template','summary','date','date');
    INSERT INTO versions VALUES(1,1,1,'{{resume_text}}','Original','date');
    INSERT INTO analyses VALUES(1,'SQL','SQL','Analyst','{}','date');
    INSERT INTO runs VALUES(1,1,1,'Existing template','summary','{{resume_text}}','SQL','old-model','demo','Old output','{"accuracy":5}',NULL,'{}','date');"""
    with sqlite3.connect(path) as conn:
        conn.executescript(schema)
    db.initialize()
    db.initialize()
    from app.main import decode_run

    with db.connect() as conn:
        row = decode_run(conn.execute("SELECT * FROM runs").fetchone())
        assert row["output_text"] == "Old output" and row["feedback"] == {"accuracy": 5}
        assert row["retrieval_snapshot"] is None
        assert (
            conn.execute("SELECT name FROM templates").fetchone()[0]
            == "Existing template"
        )
        assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0


def test_embedding_timeout_and_invalid_model(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("private-url")

    monkeypatch.setattr(httpx.Client, "post", timeout)
    with pytest.raises(llm.LLMError) as error:
        rag.embed(["x"], "RETRIEVAL_QUERY", rag.settings())
    assert error.value.status == 504 and "private-url" not in str(error.value)
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "https://bad.example")
    with pytest.raises(llm.LLMError):
        rag.settings()


def test_nonfinite_and_invalid_vectors():
    for v in [[True] * 768, [float("nan")] * 768, [float("inf")] * 768, [1e308] * 768]:
        with pytest.raises(ValueError):
            rag.normalize(v)


def test_failed_refresh_preserves_index_and_stops_generation(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)
    original = rag.documents(a["id"])
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-changed")

    def fail(*args):
        raise llm.LLMError("Provider unavailable", 502)

    monkeypatch.setattr(rag, "embed", fail)
    monkeypatch.setattr(
        llm, "generate", lambda *a: pytest.fail("Generation must not bypass retrieval")
    )
    result = client.post(
        f"/api/analysis/{a['id']}/run-prompt", json={"prompt_version_id": 1}
    )
    assert result.status_code == 502
    assert rag.documents(a["id"]) == original
    assert client.get(f"/api/analysis/{a['id']}/prompt-runs").json() == []


def test_corrupt_vectors_repaired_and_empty_retrieval_explicit(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client, "Cooking and baking")
    aid = a["id"]
    result = client.post(
        f"/api/analysis/{aid}/preview", json={"prompt_text": "{{resume_text}}"}
    ).json()
    assert result["retrieval_snapshot"]["sources"] == []
    assert "insufficient evidence" in result["rendered_prompt"]
    assert "Cooking" not in result["rendered_prompt"]
    with db.connect() as conn:
        conn.execute("UPDATE rag_chunks SET embedding='[1]'")
        conn.execute("UPDATE rag_queries SET embedding='[1]'")
    assert client.post(f"/api/analysis/{aid}/retrieve", json={}).status_code == 200


def test_literal_source_text_is_not_recursively_substituted(client, fake_embeddings):
    a = make_analysis(client, "SQL {{target_role}} <script>alert(1)</script>")
    result = client.post(
        f"/api/analysis/{a['id']}/preview", json={"prompt_text": "{{resume_text}}"}
    ).json()
    assert "{{target_role}}" in result["rendered_prompt"]
    assert "untrusted DATA" in result["rendered_prompt"]
