from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from job_bot.config import ROOT, load_profile, load_profile_context
from job_bot.job_fetcher import fetch_job_from_url
from job_bot.matcher import score_job
from job_bot.models import CandidateProfile, JobPosting
from job_bot.ollama_client import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    evaluate_with_ollama,
    fallback_evaluation,
    to_serializable_match,
)


def evaluate_job(
    profile: CandidateProfile,
    job: JobPosting,
    profile_context: str = "",
    min_score: int = 60,
    use_llm: bool = True,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_timeout: int = 120,
    profile_source: str = "config/profile.json",
    profile_context_source: str = "config/profile_context.md",
) -> dict[str, Any]:
    match = score_job(profile, job)

    llm_used = False
    if use_llm:
        try:
            llm_result = evaluate_with_ollama(
                profile=profile,
                job=job,
                match=match,
                threshold=min_score,
                model=model,
                ollama_url=ollama_url,
                timeout_seconds=ollama_timeout,
                profile_context=profile_context,
            )
            llm_used = True
        except RuntimeError as exc:
            llm_result = fallback_evaluation(match, min_score, error=str(exc))
    else:
        llm_result = fallback_evaluation(match, min_score)

    hard_vetoes = decision_vetoes(match)
    deterministic_decision = "apply" if match.score >= min_score and not hard_vetoes else "no apply"
    final_decision = (
        "apply"
        if deterministic_decision == "apply" and llm_result["decision"] == "apply"
        else "no apply"
    )

    return {
        "mode": "evaluate_only",
        "will_apply": False,
        "decision": final_decision,
        "suitable": final_decision == "apply",
        "score": match.score,
        "threshold": min_score,
        "decision_basis": {
            "final_rule": (
                "apply only when keyword_score >= threshold, no hard veto exists, "
                "and the local LLM also recommends apply"
            ),
            "profile_source": profile_source,
            "profile_context_source": profile_context_source,
            "profile_context_used_by_llm": llm_used and bool(profile_context),
            "keyword_score": match.score,
            "keyword_threshold": min_score,
            "deterministic_decision": deterministic_decision,
            "llm_recommendation": llm_result["decision"],
            "hard_vetoes": hard_vetoes,
            "evidence_used": [
                "config/profile.json candidate skills",
                "config/profile.json candidate experience/background",
                "config/profile.json interested_roles",
                "config/profile.json avoid_roles",
                "config/profile.json preferred_locations",
                "config/profile_context.md candidate guidance (LLM stage only)",
                "fetched job title",
                "fetched job page text",
                "inferred job requirements",
                "keyword match score and gaps",
            ],
        },
        "llm": {
            "used": llm_used,
            "model": model if use_llm else None,
            "ollama_url": ollama_url if use_llm else None,
            "evaluation": llm_result,
        },
        "job": {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "inferred_requirements": job.requirements,
            "description_confidence": job.description_confidence,
        },
        "match": to_serializable_match(match),
        "matched_terms": match.matched_terms,
        "missing_or_gap_terms": match.missing_terms,
        "reasons": match.reasons,
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
        "role_description_full": job.description,
    }


def evaluate_job_url(
    url: str,
    profile_path: Path | str = "config/profile.json",
    profile_context_path: Path | str = "config/profile_context.md",
    min_score: int = 60,
    fetch_timeout: int = 20,
    use_llm: bool = True,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    ollama_timeout: int = 120,
) -> dict[str, Any]:
    resolved_profile_path = Path(profile_path)
    if not resolved_profile_path.is_absolute():
        resolved_profile_path = ROOT / resolved_profile_path

    resolved_context_path = Path(profile_context_path)
    if not resolved_context_path.is_absolute():
        resolved_context_path = ROOT / resolved_context_path

    profile = load_profile(resolved_profile_path)
    profile_context = load_profile_context(resolved_context_path)
    job = fetch_job_from_url(url, timeout_seconds=fetch_timeout)

    return evaluate_job(
        profile=profile,
        job=job,
        profile_context=profile_context,
        min_score=min_score,
        use_llm=use_llm,
        model=model,
        ollama_url=ollama_url,
        ollama_timeout=ollama_timeout,
        profile_source=str(resolved_profile_path),
        profile_context_source=str(resolved_context_path),
    )


def write_evaluation(result: dict[str, Any], output_path: Path | str | None = None) -> Path:
    if output_path is None:
        output_dir = ROOT / "out" / "evaluations"
        output_dir.mkdir(parents=True, exist_ok=True)
        title = str(result.get("job", {}).get("title", "job"))
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = output_dir / f"{timestamp}-{slug(title)}.json"
    else:
        output_path = Path(output_path)
        if not output_path.is_absolute():
            output_path = ROOT / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path


def slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "job"


def decision_vetoes(match: Any) -> list[str]:
    vetoes = []
    for reason in match.reasons:
        if reason.startswith("Avoided role matched:"):
            vetoes.append(reason)
    return vetoes
