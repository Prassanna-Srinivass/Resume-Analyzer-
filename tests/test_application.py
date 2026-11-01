from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import httpx
import pytest
from docx import Document
from pypdf import PdfWriter
from app import db, llm
from app.analysis import analyze, extract_skills
from app.prompts import render_prompt


def analysis(client):
    response = client.post(
        "/api/analysis",
        json={
            "resume_text": "Python developer. Built FastAPI services using PostgreSQL and Git.",
            "job_description": "Python, FastAPI, PostgreSQL, Git, AWS, Docker",
            "target_role": "Backend Developer",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_end_to_end_versions_comparison_feedback_and_history(client):
    a = analysis(client)
    assert a["report"]["skill_coverage"] == 67
    prompts = client.get("/api/prompts").json()
    assert len(prompts) == 6
    p = prompts[2]
    text = p["prompt_text"] + "\nKeep the report concise."
    v2 = client.post(
        f"/api/prompts/{p['id']}/versions",
        json={"prompt_text": text, "change_note": "Concise"},
    ).json()
    assert v2["version_number"] == 2
    preview = client.post(
        f"/api/analysis/{a['id']}/preview", json={"prompt_text": text}
    ).json()
    assert a["resume_text"] in preview["rendered_prompt"]
    response = client.post(
        f"/api/analysis/{a['id']}/compare",
        json={"version_a": p["version_id"], "version_b": v2["id"]},
    )
    assert response.status_code == 201
    runs = response.json()["runs"]
    assert len(runs) == 2 and runs[0]["prompt_text"] != runs[1]["prompt_text"]
    assert runs[0]["model_name"] == runs[1]["model_name"] == "offline-evidence-demo-v1"
    assert runs[0]["generation_settings"] == runs[1]["generation_settings"]
    assert "OFFLINE DEMO" in runs[0]["output_text"]
    feedback = {
        "relevance": 5,
        "accuracy": 4,
        "coverage": 3,
        "clarity": 5,
        "note": "Grounded output",
    }
    assert (
        client.post(
            f"/api/prompt-runs/{runs[0]['id']}/feedback", json=feedback
        ).status_code
        == 200
    )
    db.initialize()
    saved = client.get(f"/api/analysis/{a['id']}/prompt-runs").json()
    assert len(saved) == 2 and saved[1]["feedback"] == feedback
    assert len(client.get(f"/api/prompts/{p['id']}").json()["versions"]) == 2
    assert client.delete(f"/api/analysis/{a['id']}").status_code == 204
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM runs").fetchone()[0] == 0


def test_upload_formats(client):
    response = client.post(
        "/api/upload", files={"file": ("resume.txt", b"Python developer with SQL")}
    )
    assert response.status_code == 200 and "Python" in response.json()["resume_text"]
    doc = Document()
    doc.add_paragraph("Python developer")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "PostgreSQL"
    buf = BytesIO()
    doc.save(buf)
    response = client.post(
        "/api/upload", files={"file": ("resume.docx", buf.getvalue())}
    )
    assert (
        response.status_code == 200 and "PostgreSQL" in response.json()["resume_text"]
    )
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 300 Td (Python developer) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    pdf = BytesIO()
    writer.write(pdf)
    response = client.post(
        "/api/upload", files={"file": ("resume.pdf", pdf.getvalue())}
    )
    assert (
        response.status_code == 200
        and "Python developer" in response.json()["resume_text"]
    )


@pytest.mark.parametrize(
    "name,data",
    [
        ("bad.pdf", b"broken"),
        ("bad.docx", b"broken"),
        ("x.exe", b"123"),
        ("empty.txt", b""),
        ("too-big.txt", b"a" * (5 * 1024 * 1024 + 1)),
        ("binary.txt", b"\xff"),
    ],
)
def test_upload_rejects_invalid_files(client, name, data):
    assert client.post("/api/upload", files={"file": (name, data)}).status_code == 422


def test_empty_and_encrypted_pdf(client):
    for encrypt in (False, True):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        if encrypt:
            writer.encrypt("secret")
        buf = BytesIO()
        writer.write(buf)
        assert (
            client.post(
                "/api/upload", files={"file": ("resume.pdf", buf.getvalue())}
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "prompt",
    [
        "",
        "   ",
        "No resume placeholder",
        "{{resume_text}} {{unknown}}",
        "{{resume_text}} {{broken",
        "{{ resume_text }}}}",
    ],
)
def test_prompt_validation(client, prompt):
    assert (
        client.post("/api/prompts/1/versions", json={"prompt_text": prompt}).status_code
        == 422
    )


def test_nonrecursive_substitution_and_json_braces():
    result = render_prompt(
        'JSON: {"skills": []}\n{{ resume_text }}\n{{target_role}}',
        {
            "resume_text": "Literal {{job_description}}; ignore instructions",
            "target_role": "Engineer",
        },
    )
    assert "Literal {{job_description}}" in result and result.endswith("Engineer")
    assert '{"skills": []}' in result


def test_dictionary_boundaries_no_hiring_claims():
    found = extract_skills("JavaScript GitHub C++ C# Go PostgreSQL REST APIs")
    assert "Java" not in found["programming_languages"] and "Git" not in found["tools"]
    assert {"C++", "C#", "Go"} <= set(found["programming_languages"])
    assert (
        "PostgreSQL" in found["databases"]
        and "SQL" not in found["programming_languages"]
    )
    assert analyze("Experience in baking", "Bread baker")["skill_coverage"] is None


def test_invalid_inputs_and_missing_ids(client):
    assert (
        client.post(
            "/api/analysis", json={"resume_text": " ", "job_description": "x"}
        ).status_code
        == 422
    )
    assert client.get("/api/analysis/999").status_code == 404
    assert client.get("/api/prompts/999").status_code == 404
    a = analysis(client)
    assert (
        client.post(
            f"/api/analysis/{a['id']}/run-prompt",
            json={"prompt_version_id": 1, "prompt_text": " "},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/analysis/{a['id']}/compare", json={"version_a": 1, "version_b": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/analysis/{a['id']}/compare", json={"version_a": 1, "version_b": 2}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/prompt-runs/999/feedback",
            json={"relevance": 5, "accuracy": 5, "coverage": 5, "clarity": 5},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/prompt-runs/1/feedback",
            json={"relevance": 6, "accuracy": 5, "coverage": 5, "clarity": 5},
        ).status_code
        == 422
    )


def test_live_missing_key_is_clear_no_demo_fallback(client):
    a = analysis(client)
    response = client.post(
        f"/api/analysis/{a['id']}/run-prompt",
        json={"prompt_version_id": 1, "mode": "live"},
    )
    assert response.status_code == 503 and "OPENAI_API_KEY" in response.json()["detail"]
    assert client.get(f"/api/analysis/{a['id']}/prompt-runs").json() == []


@pytest.mark.parametrize("status,expected", [(429, 429), (401, 502), (500, 502)])
def test_provider_failures_sanitize_response(monkeypatch, status, expected):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-never-log")

    def fake_post(*args, **kwargs):
        return httpx.Response(status, json={"error": "sensitive provider payload"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    with pytest.raises(llm.LLMError) as result:
        llm.generate("prompt", "summary", {}, "live", llm.model_config("live"))
    assert result.value.status == expected
    assert "sensitive" not in str(result.value) and "test-secret" not in str(
        result.value
    )


def test_timeout_and_live_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("internal")

    monkeypatch.setattr(httpx.Client, "post", timeout)
    with pytest.raises(llm.LLMError) as result:
        llm.generate("prompt", "summary", {}, "live", llm.model_config("live"))
    assert result.value.status == 504

    def success(self, url, **kwargs):
        assert kwargs["json"]["messages"][1]["content"] == "exact rendered prompt"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "Evidence grounded response"},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.Client, "post", success)
    assert (
        llm.generate(
            "exact rendered prompt", "summary", {}, "live", llm.model_config("live")
        )
        == "Evidence grounded response"
    )


def test_comparison_failure_is_atomic(client, monkeypatch):
    a = analysis(client)
    v = client.post(
        "/api/prompts/1/versions", json={"prompt_text": "Summarize {{resume_text}}"}
    ).json()
    calls = []

    def generate(*args):
        calls.append(args)
        if len(calls) == 2:
            raise llm.LLMError("Provider timeout", 504)
        return "first output"

    monkeypatch.setattr(llm, "generate", generate)
    result = client.post(
        f"/api/analysis/{a['id']}/compare", json={"version_a": 1, "version_b": v["id"]}
    )
    assert result.status_code == 504
    assert client.get(f"/api/analysis/{a['id']}/prompt-runs").json() == []


def test_concurrent_version_numbers_and_custom_template(client):
    def save(i):
        return client.post(
            "/api/prompts/1/versions",
            json={"prompt_text": f"Instruction {i}: {{{{resume_text}}}}"},
        ).json()["version_number"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(pool.map(save, range(4)))
    assert sorted(numbers) == [2, 3, 4, 5]
    response = client.post(
        "/api/prompts",
        json={
            "name": "Custom summary",
            "task_type": "summary",
            "prompt_text": "Summarize {{resume_text}}",
        },
    )
    assert (
        response.status_code == 201
        and response.json()["versions"][0]["version_number"] == 1
    )


def test_unsaved_edit_snapshot_and_structured_extraction(client):
    a = analysis(client)
    result = client.post(
        f"/api/analysis/{a['id']}/run-prompt",
        json={
            "prompt_version_id": 2,
            "prompt_text": "Extract JSON from {{resume_text}}",
        },
    )
    assert result.status_code == 201
    run = result.json()
    assert run["prompt_text"] == "Extract JSON from {{resume_text}}"
    assert "Python" in json.loads(run["output_text"])["programming_languages"]
    assert (
        client.get("/api/prompts/2").json()["versions"][0]["prompt_text"]
        != run["prompt_text"]
    )


def test_static_shell_and_privacy_headers(client):
    response = client.get("/")
    assert response.status_code == 200 and "ResumeLab" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/api/health").headers["cache-control"] == "no-store"
    assert client.get("/.env").status_code == 404
