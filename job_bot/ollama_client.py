from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from job_bot.matcher import detect_seniority_signals
from job_bot.models import CandidateProfile, JobPosting, MatchResult


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:12b"
DEFAULT_KEEP_ALIVE = "30m"


def evaluate_with_ollama(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
    threshold: int,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = 120,
    profile_context: str = "",
    keep_alive: str = DEFAULT_KEEP_ALIVE,
    num_ctx: int | None = None,
) -> dict[str, Any]:
    system_content = (
        "You evaluate job fit for a candidate. Return only valid JSON. "
        "Use decision 'APPLY' only when the job is clearly relevant, "
        "honest for the candidate profile, and worth applying to. "
        "Use decision 'NO_APPLY' when the fit is weak, misleading, "
        "too senior, unrelated, or missing important requirements. "
        "Before listing a skill as missing or as a gap, check the "
        "candidate's skills and background lists carefully — do not claim a "
        "skill is missing or limited if it, or a close equivalent, already "
        "appears there; a close equivalent belongs in transferable_matches, "
        "not missing_skills. Never invent a job requirement that is not "
        "present in the job description text given to you. If the job "
        "description is flagged as low confidence (short or possibly "
        "incomplete because the page could not be fully read), say so "
        "explicitly in 'reason', avoid confident claims about what the job "
        "does or does not require, and prefer 'NO_APPLY' rather than "
        "guessing. "
        "The job snapshot includes a "
        "'seniority_signals_detected_in_description' list, produced by a "
        "separate keyword scan of the full job text for seniority titles "
        "(Senior, Staff, Principal, Lead, Head of, Director) and "
        "years-of-experience requirements. If that list is non-empty, you "
        "must explicitly weigh it against the candidate's stated "
        "experience level and career stage (see their context below) "
        "before deciding — do not ignore it just because other parts of "
        "the description look junior-friendly. "
        "The candidate has also provided written context about their "
        "background, transferable skills, and how they want jobs "
        "evaluated. Treat it as the candidate's own judgment about "
        "what counts as a reasonable match, not as an instruction to "
        "always approve. "
        "'hard_requirement_failures' is downstream-visible: any non-empty "
        "entry there forces a 'no apply' outcome regardless of your overall "
        "decision, so only use it for requirements the candidate flatly "
        "cannot meet (e.g. a work authorization or clearance the candidate "
        "does not have, a required certification they do not hold) — never "
        "for a skill gap that is merely learnable, which belongs in "
        "'missing_skills' instead. Leave it as an empty list unless there "
        "is a genuine, material blocker."
    )
    user_content = build_evaluation_prompt(profile, job, match, threshold, profile_context)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "keep_alive": keep_alive,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_ctx": num_ctx if num_ctx is not None else estimate_num_ctx(system_content, user_content),
        },
    }
    request = Request(
        f"{ollama_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama evaluation failed: {exc}") from exc

    content = response_data.get("message", {}).get("content", "")
    return normalize_llm_result(parse_json_object(content))


def build_evaluation_prompt(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
    threshold: int,
    profile_context: str = "",
) -> str:
    candidate_snapshot = {
        "name": profile.name,
        "location": profile.location,
        "summary": profile.cv_summary,
        "skills": profile.skills,
        "background": profile.background,
        "certificates": profile.certificates,
        "interested_roles": profile.interested_roles,
        "avoid_roles": profile.avoid_roles,
        "preferred_locations": profile.preferred_locations,
        "work_authorization": profile.work_authorization,
    }
    job_snapshot = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description_excerpt": job.description[:6000],
        "description_confidence": job.description_confidence,
        "inferred_requirements": job.requirements,
        "seniority_signals_detected_in_description": detect_seniority_signals(job.description),
    }
    score_snapshot = {
        "keyword_score": match.score,
        "threshold": threshold,
        "matched_terms": match.matched_terms,
        "missing_or_gap_terms": match.missing_terms,
        "score_reasons": match.reasons,
    }

    context_section = (
        f"\n\nCandidate's own context and evaluation guidance:\n{profile_context.strip()}"
        if profile_context.strip()
        else ""
    )

    return (
        "Evaluate this job fit. Return exactly this JSON schema:\n"
        "{\n"
        '  "decision": "APPLY" | "NO_APPLY",\n'
        '  "score": 0-100 (your own overall fit score),\n'
        '  "confidence": 0-1 (how confident you are in this evaluation),\n'
        '  "direct_matches": ["requirement the candidate clearly already meets"],\n'
        '  "transferable_matches": [\n'
        '    {"required": "job requirement", "candidate_has": "the candidate\'s closest '
        'equivalent experience", "gap": "small" | "medium" | "large"}\n'
        "  ],\n"
        '  "missing_skills": [\n'
        '    {"skill": "skill the candidate does not show", "importance": "low" | "medium" | "high"}\n'
        "  ],\n"
        '  "hard_requirement_failures": ["requirement the candidate flatly cannot meet — usually []"],\n'
        '  "experience_fit": "under" | "good" | "over",\n'
        '  "interest_fit": "poor" | "fair" | "good" | "excellent",\n'
        '  "reason": "one short paragraph explaining the decision"\n'
        "}\n\n"
        f"Candidate:\n{json.dumps(candidate_snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"Job:\n{json.dumps(job_snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"Keyword scoring:\n{json.dumps(score_snapshot, ensure_ascii=False, indent=2)}"
        f"{context_section}"
    )


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(f"Ollama did not return a JSON object: {content[:500]}")

    parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama returned JSON, but not an object.")
    return parsed


def normalize_llm_result(result: dict[str, Any]) -> dict[str, Any]:
    decision = str(result.get("decision", "")).strip().casefold().replace("_", " ")
    if decision not in {"apply", "no apply"}:
        decision = "no apply"

    return {
        "decision": decision,
        "score": clamp_int(result.get("score", 0), 0, 100),
        "confidence": clamp_float(result.get("confidence", 0.0), 0.0, 1.0),
        "direct_matches": list_of_strings(result.get("direct_matches", [])),
        "transferable_matches": list_of_transferable_matches(result.get("transferable_matches", [])),
        "missing_skills": list_of_missing_skills(result.get("missing_skills", [])),
        "hard_requirement_failures": list_of_strings(result.get("hard_requirement_failures", [])),
        "experience_fit": str(result.get("experience_fit", "")).strip().casefold(),
        "interest_fit": str(result.get("interest_fit", "")).strip().casefold(),
        "reason": str(result.get("reason", "")).strip(),
    }


def list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def clamp_int(value: Any, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return low


def clamp_float(value: Any, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def list_of_transferable_matches(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    matches = []
    for item in value:
        if not isinstance(item, dict):
            continue
        required = str(item.get("required", "")).strip()
        candidate_has = str(item.get("candidate_has", "")).strip()
        if not required or not candidate_has:
            continue
        gap = str(item.get("gap", "")).strip().casefold()
        if gap not in {"small", "medium", "large"}:
            gap = "medium"
        matches.append({"required": required, "candidate_has": candidate_has, "gap": gap})
    return matches


def list_of_missing_skills(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    skills = []
    for item in value:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", "")).strip()
        if not skill:
            continue
        importance = str(item.get("importance", "")).strip().casefold()
        if importance not in {"low", "medium", "high"}:
            importance = "medium"
        skills.append({"skill": skill, "importance": importance})
    return skills


def fallback_evaluation(match: MatchResult, threshold: int, error: str | None = None) -> dict[str, Any]:
    decision = "apply" if match.score >= threshold else "no apply"
    result = {
        "decision": decision,
        "score": match.score,
        "confidence": round(min(0.95, max(0.3, match.score / 100)), 2),
        "direct_matches": match.matched_terms[:8],
        "transferable_matches": [],
        "missing_skills": [{"skill": term, "importance": "medium"} for term in match.missing_terms[:8]],
        "hard_requirement_failures": [],
        "experience_fit": "unknown",
        "interest_fit": "unknown",
        "reason": (
            "Fallback decision based on keyword scoring because the local LLM "
            "was not used or was unavailable."
        ),
    }
    if error:
        result["llm_error"] = error
    return result


def to_serializable_match(match: MatchResult) -> dict[str, Any]:
    return asdict(match)


NUM_CTX_BUCKETS = (4096, 8192, 16384, 32768, 65536)


def estimate_num_ctx(*texts: str) -> int:
    """Ollama defaults to a small context window regardless of a model's max
    supported length, silently truncating long prompts. Size it to the
    actual prompt so the full candidate profile, job text, and
    profile_context.md guidance are never dropped."""
    estimated_tokens = sum(len(text) for text in texts) // 3 + 1024
    for bucket in NUM_CTX_BUCKETS:
        if estimated_tokens <= bucket:
            return bucket
    return NUM_CTX_BUCKETS[-1]


def compute_batch_num_ctx(
    profile: CandidateProfile,
    jobs: list[JobPosting],
    profile_context: str = "",
    threshold: int = 60,
) -> int:
    """Ollama has to reallocate its KV cache — effectively reloading the
    model — whenever a request's num_ctx differs from the one currently
    loaded. Evaluating each job with its own tightly-sized num_ctx (as a
    single evaluate_job_url call does) would force a reload on almost every
    job in a batch. Sizing once for the largest prompt in the batch and
    reusing that bucket for every call keeps the same context loaded for
    the whole run."""
    if not jobs:
        return NUM_CTX_BUCKETS[0]
    placeholder_match = MatchResult(score=0, matched_terms=[], missing_terms=[], reasons=[])
    return max(
        estimate_num_ctx(
            build_evaluation_prompt(profile, job, placeholder_match, threshold, profile_context)
        )
        for job in jobs
    )


def unload_model(model: str, ollama_url: str = DEFAULT_OLLAMA_URL, timeout_seconds: int = 30) -> None:
    """Explicitly evict the model from Ollama's memory once a batch run is
    done, instead of leaving it resident in RAM until keep_alive expires."""
    request = Request(
        f"{ollama_url.rstrip('/')}/api/generate",
        data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds):
            pass
    except (HTTPError, URLError, TimeoutError):
        pass
