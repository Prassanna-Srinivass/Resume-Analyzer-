"""Server-side OpenAI integration. Demo output is explicitly non-generative."""

import json
import os
import httpx
from .prompts import GUARD


class LLMError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def model_config(mode):
    if mode == "demo":
        return {"model": "offline-evidence-demo-v1", "temperature": None}
    return {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "temperature": 0.2}


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
    if mode == "demo":
        return demo_output(task, analysis)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise LLMError(
            "Live AI is not configured. Add OPENAI_API_KEY to the backend .env file and restart, or choose Offline demo.",
            503,
        )
    try:
        with httpx.Client(timeout=httpx.Timeout(60, connect=10)) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": config["model"],
                    "temperature": config["temperature"],
                    "max_tokens": 1800,
                    "messages": [
                        {"role": "system", "content": GUARD},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
        if response.status_code == 429:
            raise LLMError(
                "The AI provider rate limit or quota was reached. Check your API billing or try again later.",
                429,
            )
        if response.status_code in (401, 403):
            raise LLMError(
                "The AI provider rejected the server credentials. Check OPENAI_API_KEY and model access.",
                502,
            )
        if response.is_error:
            raise LLMError(
                "The AI provider could not complete the request. Check the configured model and retry."
            )
        body = response.json()
        choice = body["choices"][0]
        output = choice["message"]["content"]
        if not isinstance(output, str) or not output.strip():
            raise ValueError("Empty response")
        if choice.get("finish_reason") == "length":
            output += "\n\n[Output truncated at the provider token limit. Narrow the prompt and rerun.]"
        return output
    except httpx.TimeoutException as exc:
        raise LLMError(
            "The AI request timed out after 60 seconds. Please retry.", 504
        ) from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(
            "The AI provider returned an unavailable or invalid response. Please retry."
        ) from exc
