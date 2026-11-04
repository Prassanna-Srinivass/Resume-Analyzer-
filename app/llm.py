"""Server-side Google Gemini integration. Demo output is explicitly non-generative."""

import json
import os
import re
import httpx
from .prompts import GUARD


class LLMError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def model_config(mode, temperature=None):
    if mode == "demo":
        return {"model": "offline-evidence-demo-v1", "temperature": None}
    config = {
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip(),
        "max_output_tokens": 4096,
    }
    if temperature is not None:
        config["temperature"] = temperature
    return config


def demo_output(task, analysis):
    report = analysis["report"]
    groups = report["skills"]
    all_skills = [s for values in groups.values() for s in values]
    matched = ", ".join(report["matched_skills"]) or "None detected"
    missing = ", ".join(report["not_demonstrated"]) or "None in the limited dictionary"
    excerpts = "\n".join(
        f'- {skill}: "{quote}"' for skill, quote in report["evidence"].items()
    )
    if task == "extraction":
        return json.dumps(groups, indent=2)
    header = "OFFLINE DEMO — deterministic evidence report, not an LLM response.\nEdited prompt instructions do not change demo generation. Use Live AI to evaluate prompt quality.\n\n"
    if task == "summary":
        return (
            header
            + "RESUME EXCERPT\n"
            + analysis["resume_text"][:700]
            + "\n\nEXPLICITLY DETECTED SKILLS\n"
            + (", ".join(all_skills) or "None detected")
            + "\n\nThis is an extractive preview; it does not infer years of experience or achievements."
        )
    if task in {"matching", "explanation"}:
        coverage = report["skill_coverage"]
        return (
            header
            + f"JOB SKILL COVERAGE: {str(coverage)+'%' if coverage is not None else 'N/A'}\n\nMATCHED\n{matched}\n\nRESUME EVIDENCE\n{excerpts or 'No explicit matches detected.'}\n\nNOT DEMONSTRATED\n{missing}\n\nPARTIAL MATCHES\nNot assessed by the offline dictionary baseline; human or live-model review is needed.\n\nCoverage includes only detected dictionary skills. Missing keywords do not establish a lack of ability."
        )
    if task == "improvement":
        return (
            header
            + f"PRIORITY IMPROVEMENTS\n1. Put supported skills relevant to the role near the top: {matched}.\n2. Describe your own contribution to each listed project. Add outcomes only when you can verify them.\n3. Review these requirements for missing evidence: {missing}. Add examples only if truthful.\n\nSUGGESTED WORDING (explicit skills only)\nSkills: {', '.join(all_skills) or 'No skills detected; review the resume manually.'}\n\nMISSING EVIDENCE\nDo not invent metrics, experience, or qualifications to fill gaps."
        )
    questions = [
        f"Describe a project where you used {s}. What was your own contribution?"
        for s in report["matched_skills"][:3]
    ]
    questions += [
        f"The role mentions {s}. What experience, if any, could you demonstrate?"
        for s in report["not_demonstrated"][:3]
    ]
    questions += [
        "Which listed project best demonstrates your approach to solving problems?",
        "How would you explain a technical tradeoff from your stated experience?",
        "What would you want to learn first in this role?",
        "How do you verify the quality of your work?",
        "Describe a collaboration challenge from your stated experience.",
        "What questions do you have about the role?",
    ]
    return (
        header
        + "INTERVIEW QUESTIONS\n"
        + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions[:6]))
    )


def generate(prompt, task, analysis, mode, config):
    """Generate server-side through Gemini; never fall back to a demo on failure."""
    if mode != "live":
        raise LLMError(
            "All new runs require live Gemini generation with resume retrieval.", 422
        )
    system_guard = GUARD
    if config.get("rag_enabled"):
        from .rag import RAG_GUARD

        system_guard = RAG_GUARD
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "Live AI is not configured. Add GEMINI_API_KEY to the backend .env file and restart.",
            503,
        )
    model = config["model"]
    if not re.fullmatch(r"gemini-[A-Za-z0-9._-]+", model):
        raise LLMError(
            "GEMINI_MODEL must be a model ID such as gemini-3.5-flash-lite, without a URL or models/ prefix.",
            503,
        )
    generation_config = {"maxOutputTokens": config.get("max_output_tokens", 4096)}
    if "temperature" in config:
        generation_config["temperature"] = config["temperature"]
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=10)) as client:
            response = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json={
                    "systemInstruction": {"parts": [{"text": system_guard}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": generation_config,
                },
            )
        if response.status_code == 429:
            raise LLMError(
                "Gemini rate limit or quota reached. Check your Google API billing/quota or retry later.",
                429,
            )
        if response.status_code in (400, 401, 403):
            raise LLMError(
                "Gemini rejected the request. Check GEMINI_API_KEY, GEMINI_MODEL, and access for your Google API project."
            )
        if response.status_code == 404:
            raise LLMError(
                "The configured Gemini model was not found or is not available to this API project. Check GEMINI_MODEL."
            )
        if response.is_error:
            raise LLMError("Gemini could not complete the request. Please retry later.")
        body = response.json()
        if body.get("promptFeedback", {}).get("blockReason"):
            raise LLMError(
                "Gemini blocked this request. Review the supplied content and prompt before retrying.",
                422,
            )
        candidate = body["candidates"][0]
        finish = candidate.get("finishReason", "")
        if finish not in ("STOP", "MAX_TOKENS"):
            raise LLMError(
                "Gemini could not return a complete response for this request. Review the prompt and retry.",
                422,
            )
        parts = candidate.get("content", {}).get("parts", [])
        output = "".join(
            part["text"]
            for part in parts
            if isinstance(part.get("text"), str) and not part.get("thought")
        ).strip()
        if not output:
            raise ValueError("Empty response")
        if finish == "MAX_TOKENS":
            output += "\n\n[Output truncated at the Gemini token limit. Narrow the prompt and rerun.]"
        return output
    except httpx.TimeoutException as exc:
        raise LLMError(
            "The Gemini request timed out after 60 seconds. Please retry.", 504
        ) from exc
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        AttributeError,
    ) as exc:
        raise LLMError(
            "Gemini returned an unavailable or invalid response. Please retry."
        ) from exc
