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


def upload(
    client, aid, text="Used SQL joins to validate sales totals.", name="project.txt"
):
    return client.post(
        f"/api/analysis/{aid}/documents", files={"file": (name, text.encode())}
    )


def test_rag_index_retrieve_run_compare_and_reload(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)
    aid = a["id"]
    indexed = upload(client, aid)
    assert indexed.status_code == 201
    doc = indexed.json()["document"]
    assert doc["chunk_count"] == 1
    assert upload(client, aid).json()["cached"] is True
    assert len(fake_embeddings) == 1
    assert client.post(f"/api/analysis/{aid}/index-resume").status_code == 201
    assert len(client.get(f"/api/analysis/{aid}/documents").json()) == 2
    retrieved = client.post(
        f"/api/analysis/{aid}/retrieve",
        json={"rag_query": "SQL validation", "top_k": 3},
    ).json()
    assert retrieved["sources"][0]["source_id"] == f"D{doc['id']}-C1"
    assert retrieved["sources"][0]["text"] == "Used SQL joins to validate sales totals."
    assert retrieved["sources"][0]["page"] is None
    p = client.get("/api/prompts").json()[0]
    v = client.post(
        f"/api/prompts/{p['id']}/versions",
        json={
            "prompt_text": p["prompt_text"]
            + "\n{{retrieved_context}}\nUse three bullets."
        },
    ).json()
    prompts = []

    def generate(prompt, task, analysis, mode, config):
        assert config["rag_enabled"] is True
        assert "[RESUME]" in prompt and "SQL joins" in prompt
        prompts.append(prompt)
        return f"SQL validation is documented [D{doc['id']}-C1]. Python appears in the resume [RESUME]."

    monkeypatch.setattr(llm, "generate", generate)
    before = len(fake_embeddings)
    response = client.post(
        f"/api/analysis/{aid}/compare",
        json={
            "version_a": p["version_id"],
            "version_b": v["id"],
            "mode": "live",
            "rag_enabled": True,
            "rag_query": "SQL validation",
        },
    )
    assert response.status_code == 201, response.text
    runs = response.json()["runs"]
    assert len(fake_embeddings) == before + 1  # one query embedding for both prompts
    assert runs[0]["retrieval_snapshot"] == runs[1]["retrieval_snapshot"]
    assert runs[0]["retrieval_snapshot"]["citation_check"]["warnings"] == []
    assert len(prompts) == 2 and prompts[0] != prompts[1]
    db.initialize()
    restored = client.get(f"/api/analysis/{aid}/prompt-runs").json()
    assert restored[0]["retrieval_snapshot"] == runs[1]["retrieval_snapshot"]
    assert (
        client.delete(f"/api/analysis/{aid}/documents/{doc['id']}").status_code == 204
    )
    # Immutable evidence survives document removal; no longer used for new queries.
    assert (
        client.get(f"/api/analysis/{aid}/prompt-runs").json()[0]["retrieval_snapshot"]
        == restored[0]["retrieval_snapshot"]
    )
    assert all(
        s["document_id"] != doc["id"]
        for s in client.post(f"/api/analysis/{aid}/retrieve", json={}).json()["sources"]
    )
    assert client.delete(f"/api/analysis/{aid}").status_code == 204
    with db.connect() as conn:
        for table in ["rag_documents", "rag_chunks", "runs"]:
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_analysis_isolation_and_settings_changes(client, fake_embeddings, monkeypatch):
    a, b = make_analysis(client), make_analysis(
        client, "Different candidate, no SQL evidence."
    )
    doc = upload(client, a["id"]).json()["document"]
    assert client.get(f"/api/analysis/{b['id']}/documents").json() == []
    assert (
        client.delete(f"/api/analysis/{b['id']}/documents/{doc['id']}").status_code
        == 404
    )
    assert client.post(f"/api/analysis/{b['id']}/retrieve", json={}).status_code == 422
    monkeypatch.setenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-other")
    assert client.post(f"/api/analysis/{a['id']}/retrieve", json={}).status_code == 422


def test_index_failure_no_partial_writes(client, monkeypatch):
    a = make_analysis(client)

    def fail(*args):
        raise llm.LLMError("Embedding service unavailable")

    monkeypatch.setattr(rag, "embed", fail)
    assert upload(client, a["id"]).status_code == 502
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM rag_chunks").fetchone()[0] == 0


def test_missing_key_demo_guard_and_empty_collection(client):
    a = make_analysis(client)
    aid = a["id"]
    p = client.get("/api/prompts").json()[0]
    assert client.post(f"/api/analysis/{aid}/index-resume").status_code == 503
    assert (
        client.post(
            f"/api/analysis/{aid}/run-prompt",
            json={
                "prompt_version_id": p["version_id"],
                "mode": "demo",
                "rag_enabled": True,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/analysis/{aid}/run-prompt",
            json={
                "prompt_version_id": p["version_id"],
                "mode": "live",
                "rag_enabled": True,
            },
        ).status_code
        == 422
    )
    assert client.get(f"/api/analysis/{aid}/prompt-runs").json() == []


def test_preview_sources_literal_placeholders_and_citations(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)
    aid = a["id"]
    upload(client, aid, "SQL evidence {{target_role}} <script>alert(1)</script>")
    body = {
        "prompt_text": "Summarize {{resume_text}}\n{{retrieved_context}}",
        "rag_enabled": True,
    }
    response = client.post(f"/api/analysis/{aid}/preview", json=body)
    assert response.status_code == 200
    result = response.json()
    assert "{{target_role}}" in result["rendered_prompt"]
    assert "SQL evidence" in result["rendered_prompt"]
    assert len(result["retrieval_snapshot"]["sources"]) == 1
    snap = result["retrieval_snapshot"]
    assert rag.citation_check("Claim [D999-C1]", snap)["warnings"]
    assert rag.citation_check("No citation", snap)["warnings"]
    assert rag.citation_check("Resume [RESUME]", snap)["warnings"] == []
    disabled = client.post(
        f"/api/analysis/{aid}/preview", json={"prompt_text": body["prompt_text"]}
    ).json()
    assert (
        "RAG is disabled" in disabled["rendered_prompt"]
        and disabled["retrieval_snapshot"] is None
    )


def test_comparison_provider_failure_preserves_atomicity(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)
    aid = a["id"]
    upload(client, aid)
    p = client.get("/api/prompts").json()[0]
    v = client.post(
        f"/api/prompts/{p['id']}/versions",
        json={"prompt_text": p["prompt_text"] + "\nShort."},
    ).json()
    count = 0

    def generate(*args):
        nonlocal count
        count += 1
        if count == 2:
            raise llm.LLMError("Failed")
        return "First [RESUME]"

    monkeypatch.setattr(llm, "generate", generate)
    result = client.post(
        f"/api/analysis/{aid}/compare",
        json={
            "version_a": p["version_id"],
            "version_b": v["id"],
            "mode": "live",
            "rag_enabled": True,
        },
    )
    assert result.status_code == 502
    assert client.get(f"/api/analysis/{aid}/prompt-runs").json() == []


def test_document_validation_and_scope_before_provider(client, fake_embeddings):
    a = make_analysis(client)
    assert upload(client, 999).status_code == 404
    assert upload(client, a["id"], "", "empty.txt").status_code == 422
    assert upload(client, a["id"], "invalid", "bad.exe").status_code == 422
    assert upload(client, a["id"], "a" * (5 * 1024 * 1024 + 1)).status_code == 422
    assert fake_embeddings == []
    for k in [0, 9, True]:
        assert (
            client.post(
                f"/api/analysis/{a['id']}/retrieve", json={"top_k": k}
            ).status_code
            == 422
        )


def test_chunking_pdf_pages_docx_and_overlap(client, fake_embeddings):
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in ["SQL validation project", "Power BI dashboard"]:
        page = writer.add_blank_page(width=400, height=400)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 200 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    buf = BytesIO()
    writer.write(buf)
    sections = extract_sections("two.pdf", buf.getvalue())
    assert [s["page"] for s in sections] == [1, 2]
    aid = make_analysis(client)["id"]
    assert (
        client.post(
            f"/api/analysis/{aid}/documents",
            files={"file": ("two.pdf", buf.getvalue())},
        ).status_code
        == 201
    )
    result = client.post(
        f"/api/analysis/{aid}/retrieve", json={"rag_query": "SQL dashboards"}
    ).json()
    assert {s["page"] for s in result["sources"]} == {1, 2}
    doc = Document()
    doc.add_paragraph("SQL project")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "Validation"
    buf = BytesIO()
    doc.save(buf)
    assert "Validation" in extract_sections("project.docx", buf.getvalue())[0]["text"]
    chunks = rag.chunk_sections([{"text": "A" * 4000, "page": 1}])
    assert all(len(c["text"]) <= rag.CHUNK_SIZE for c in chunks)
    assert sum(len(c["text"]) for c in chunks) == 4000 + rag.OVERLAP * (len(chunks) - 1)


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


def test_index_limit_duplicate_concurrency_and_restart(
    client, fake_embeddings, monkeypatch
):
    a = make_analysis(client)

    def index(_):
        return rag.index_document(
            a, "project.txt", [{"text": "SQL proof", "page": None}]
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(index, range(2)))
    assert len(rag.documents(a["id"])) == 1
    assert sorted(r["cached"] for r in results) == [False, True]
    db.initialize()
    assert len(rag.documents(a["id"])) == 1
    monkeypatch.setattr(rag, "MAX_DOCUMENTS", 1)
    assert upload(client, a["id"], "Different SQL evidence").status_code == 422


def test_no_positive_retrieval_and_corrupt_index(client, fake_embeddings):
    a = make_analysis(client)
    aid = a["id"]
    upload(client, aid, "Cooking baking")
    assert (
        client.post(f"/api/analysis/{aid}/retrieve", json={"rag_query": "SQL"}).json()[
            "sources"
        ]
        == []
    )
    with db.connect() as conn:
        conn.execute("UPDATE rag_chunks SET embedding='[1]' ")
    result = client.post(f"/api/analysis/{aid}/retrieve", json={})
    assert result.status_code == 422 and "invalid" in result.json()["detail"]


def test_system_guard_allows_supporting_evidence(monkeypatch):
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
