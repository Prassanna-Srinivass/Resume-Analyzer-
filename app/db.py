"""One SQLite database for templates, immutable versions, analyses and runs."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .prompts import seed_templates


@contextmanager
def connect():
    path = Path(os.getenv("DATABASE_PATH", "data/resume_analyzer.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, task_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY, template_id INTEGER NOT NULL REFERENCES templates(id),
            version_number INTEGER NOT NULL, prompt_text TEXT NOT NULL, change_note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(template_id, version_number));
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY, resume_text TEXT NOT NULL, job_description TEXT NOT NULL,
            target_role TEXT NOT NULL, report TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
            prompt_version_id INTEGER NOT NULL REFERENCES versions(id), prompt_name TEXT NOT NULL,
            task_type TEXT NOT NULL, prompt_text TEXT NOT NULL, rendered_prompt TEXT NOT NULL,
            model_name TEXT NOT NULL, mode TEXT NOT NULL, output_text TEXT NOT NULL,
            feedback TEXT, comparison_id TEXT, generation_settings TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE INDEX IF NOT EXISTS runs_analysis ON runs(analysis_id);
        """)
        db.executescript("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
            filename TEXT NOT NULL, kind TEXT NOT NULL, fingerprint TEXT NOT NULL,
            embedding_model TEXT NOT NULL, dimensions INTEGER NOT NULL, chunk_count INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(analysis_id, fingerprint));
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
            position INTEGER NOT NULL, page INTEGER, text TEXT NOT NULL, embedding TEXT NOT NULL,
            UNIQUE(document_id, position));
        CREATE TABLE IF NOT EXISTS rag_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
            fingerprint TEXT NOT NULL, embedding TEXT NOT NULL,
            UNIQUE(analysis_id, fingerprint));
        CREATE INDEX IF NOT EXISTS rag_documents_analysis ON rag_documents(analysis_id);
        CREATE INDEX IF NOT EXISTS rag_chunks_document ON rag_chunks(document_id);
        """)
        db.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in db.execute("PRAGMA table_info(runs)")}
        if "retrieval_snapshot" not in columns:
            db.execute("ALTER TABLE runs ADD COLUMN retrieval_snapshot TEXT")
        if db.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 0:
            for name, task, prompt in seed_templates():
                tid = db.execute(
                    "INSERT INTO templates(name,task_type) VALUES (?,?)", (name, task)
                ).lastrowid
                db.execute(
                    "INSERT INTO versions(template_id,version_number,prompt_text,change_note) VALUES (?,1,?,?)",
                    (tid, prompt, "Initial evidence-based template"),
                )
