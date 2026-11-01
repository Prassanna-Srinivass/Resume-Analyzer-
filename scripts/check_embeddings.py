"""One synthetic embedding request; no resume, database write or key disclosure.

Run from the project root with your venv: python scripts/check_embeddings.py
Uses the project's .env and configured embedding model. API quota may apply.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
from app import rag
from app.llm import LLMError


def main():
    try:
        config = rag.settings()
        vectors = rag.embed(["SQL data validation test."], "RETRIEVAL_DOCUMENT", config)
    except LLMError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "model": config["model"],
                "vectors": len(vectors),
                "dimensions": len(vectors[0]),
                "database_modified": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
