"""Transparent lexical baseline, not a semantic model or hiring score."""

import math
import re
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from pypdf import PdfReader
from docx import Document

MAX_UPLOAD = 5 * 1024 * 1024
GROUPS = {
    "programming_languages": [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C++",
        "C#",
        "Go",
        "Rust",
        "SQL",
        "R",
    ],
    "frameworks": [
        "FastAPI",
        "Flask",
        "Django",
        "React",
        "Angular",
        "Vue",
        "Node.js",
        "PyTorch",
        "TensorFlow",
    ],
    "databases": ["PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "ChromaDB"],
    "tools": [
        "Git",
        "GitHub",
        "Docker",
        "Kubernetes",
        "AWS",
        "Azure",
        "GCP",
        "Linux",
        "Excel",
        "Power BI",
    ],
    "other_skills": [
        "REST API",
        "Machine Learning",
        "NLP",
        "RAG",
        "Data Analysis",
        "Communication",
        "Leadership",
        "Testing",
        "Agile",
    ],
}
ALIASES = {
    "PostgreSQL": ["postgres"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "REST API": ["rest api", "rest apis", "restful"],
    "Node.js": ["nodejs", "node.js"],
    "NLP": ["natural language processing"],
    "GCP": ["google cloud"],
    "Machine Learning": ["machine learning"],
}


def skill_pattern(skill):
    words = set([skill.lower()] + ALIASES.get(skill, []))
    return re.compile(
        r"(?<![\w+#])(?:"
        + "|".join(re.escape(x) for x in sorted(words))
        + r")(?![\w+#])",
        re.I,
    )


def extract_skills(text):
    return {
        group: [s for s in skills if skill_pattern(s).search(text)]
        for group, skills in GROUPS.items()
    }


def flatten(groups):
    return [skill for values in groups.values() for skill in values]


def analyze(resume, job):
    skills = extract_skills(resume)
    found = flatten(skills)
    required = flatten(extract_skills(job))
    matched = [s for s in required if s in found]
    missing = [s for s in required if s not in found]
    lines = [s.strip() for s in re.split(r"[\n;]", resume) if s.strip()]
    evidence = {
        s: next((line[:350] for line in lines if skill_pattern(s).search(line)), "")
        for s in matched
    }
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "with",
        "for",
        "is",
        "on",
        "as",
        "at",
    }

    def counts(t):
        return Counter(
            w for w in re.findall(r"[a-z][a-z0-9+#.]*", t.lower()) if w not in stop
        )

    a, b = counts(resume), counts(job)
    norm = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    cosine = sum(v * b[k] for k, v in a.items()) / norm if norm else 0
    return {
        "skills": skills,
        "required_skills": required,
        "matched_skills": matched,
        "not_demonstrated": missing,
        "evidence": evidence,
        "skill_coverage": (
            round(100 * len(matched) / len(required)) if required else None
        ),
        "lexical_similarity": round(100 * cosine, 1),
        "method": "Explicit dictionary skill detection and bag-of-words cosine similarity. Not semantic similarity, ATS prediction, or a hiring recommendation.",
    }


def extract_file(filename, data):
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("Upload a nonempty file up to 5 MB.")
    ext = Path(filename or "").suffix.lower()
    try:
        if ext == ".txt":
            text = data.decode("utf-8-sig")
        elif ext == ".pdf":
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError(
                    "Password-protected PDFs are not supported. Upload an unlocked copy."
                )
            if len(reader.pages) > 40:
                raise ValueError("PDFs must have at most 40 pages.")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            with ZipFile(BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 20 * 1024 * 1024:
                    raise ValueError("The expanded DOCX is too large (20 MB maximum).")
            doc = Document(BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            parts += [
                " | ".join(c.text for c in row.cells)
                for table in doc.tables
                for row in table.rows
            ]
            text = "\n".join(parts)
        else:
            raise ValueError("Supported file types: PDF, DOCX, and UTF-8 TXT.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "Could not read this file. Upload a valid PDF, DOCX, or UTF-8 TXT."
        ) from exc
    if not text.strip():
        raise ValueError(
            "No readable text found. Scanned PDFs need OCR first, or paste the text."
        )
    if len(text) > 50000:
        raise ValueError("Extracted resume exceeds 50,000 characters.")
    return text.strip()
