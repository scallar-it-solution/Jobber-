from __future__ import annotations

import re
from typing import Any

from common.config import load_yaml


def _flatten_profile(profile: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in profile.items():
        if isinstance(value, list):
            parts.append(f"{key}: {', '.join(str(item) for item in value)}")
        else:
            parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _configured_answer(question: str) -> str | None:
    bank = load_yaml("config/screening_answers.yaml")
    normalized = question.strip().lower()
    for item in bank.get("answers", []):
        pattern = str(item.get("pattern", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not pattern or not answer:
            continue
        try:
            if re.search(pattern, question, re.IGNORECASE):
                return answer
        except re.error:
            if pattern.lower() in normalized:
                return answer
    return None


def _role_summary(profile: dict[str, Any]) -> str:
    roles = profile.get("target_roles") or ["Data Engineer", "AI Engineer"]
    years = profile.get("years_experience", "3")
    return (
        f"I have {years} years of experience across {', '.join(roles[:3])} work, "
        "with hands-on delivery in Python, SQL, data pipelines, cloud workflows, "
        "analytics engineering, and AI-enabled automation."
    )


def answer_screening_question(question: str, profile: dict[str, Any]) -> str:
    configured = _configured_answer(question)
    if configured:
        return configured.format(**profile)

    q = question.lower()
    if any(term in q for term in ["salary", "compensation", "ctc", "expected pay"]):
        inr = profile.get("salary_min_inr")
        usd = profile.get("salary_min_usd")
        return (
            "My expected compensation is aligned with the role scope. "
            f"As a guide, I am targeting INR {inr:,}+ locally or USD {usd:,}+ "
            "for US/global remote roles."
        )

    if any(term in q for term in ["notice", "join", "available", "start"]):
        return f"I am available to start {profile.get('notice_period', 'immediately')}."

    if any(term in q for term in ["work authorization", "visa", "sponsorship"]):
        return (
            "I can discuss work authorization details based on the role location and engagement model. "
            "For India-based and remote contract opportunities, I am available without sponsorship."
        )

    if any(term in q for term in ["relocate", "location", "remote", "hybrid"]):
        locations = ", ".join(profile.get("target_locations", []))
        return f"I am based in {profile.get('location')} and open to opportunities in {locations}."

    if any(term in q for term in ["experience", "years", "background"]):
        return _role_summary(profile)

    if any(term in q for term in ["why", "interested", "fit"]):
        return (
            _role_summary(profile)
            + " I am interested in roles where I can build reliable data systems and practical AI workflows that create measurable business value."
        )

    return (
        _role_summary(profile)
        + " I would be happy to discuss the most relevant project examples during the interview process."
    )


def build_codex_review_prompt(question: str, profile: dict[str, Any]) -> str:
    return (
        "Draft a concise, honest 1-3 sentence job-application screening answer.\n\n"
        f"Question:\n{question}\n\n"
        f"Candidate profile:\n{_flatten_profile(profile)}\n"
    )

