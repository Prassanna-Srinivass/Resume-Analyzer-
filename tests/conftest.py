import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import rag


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_EMBEDDING_MODEL", raising=False)
    # Deterministic provider boundary; integration tests do not spend API quota.
    monkeypatch.setattr(
        rag,
        "embed",
        lambda texts, task, config: [[1.0] + [0.0] * 767 for text in texts],
    )
    with TestClient(app) as client:
        yield client
