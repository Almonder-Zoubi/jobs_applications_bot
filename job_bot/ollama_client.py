from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from job_bot.matcher import detect_seniority_signals
from job_bot.models import CandidateProfile, JobPosting, MatchResult


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


def evaluate_with_ollama(
    profile: CandidateProfile,
    job: JobPosting,
    match: MatchResult,
    threshold: int,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    timeout_seconds: int = 120,
    profile_context: str = "",
) -> dict[str, Any]:
    system_content = (
        "You evaluate job fit for a candidate. Return only valid JSON. "
        "Use decision 'apply' only when the job is clearly relevant, "
        "honest for the candidate profile, and worth applying to. "
        "Use decision 'no apply' when the fit is weak, misleading, "
        "too senior, unrelated, or missing important requirements. "
        "Before listing a concern about a missing or weak skill, check the "
        "candidate's skills and background lists carefully — do not claim a "
        "skill is missing or limited if it, or a close equivalent, already "
        "appears there. Never invent a job requirement that is not present "
        "in the job description text given to you. If the job description "
        "is flagged as low confidence (short or possibly incomplete because "
        "the page could not be fully read), say so explicitly in "
        "fit_summary, avoid confident claims about what the job does or "
        "does not require, and prefer 'no apply' with a "
        "recommended_next_step to check the original posting manually "
        "rather than guessing. "
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
        "The 'concerns' field is downstream-visible: any evaluation "
        "with a non-empty 'concerns' list gets routed to a "
        "'needs manual review' queue instead of the clean apply list, so "
        "only put something there if it is a genuine, material reason to "
        "hesitate before applying. Leave it as an empty list when the fit "
        "is simply good — do not restate a strength, a neutral fact, or "
        "the absence of a problem as if it were a concern (e.g. 'the "
        "candidate's exact seniority isn't stated' or 'the job is junior "
        "and so is the candidate' are not concerns)."
    )
    user_content = build_evaluation_prompt(profile, job, match, threshold, profile_context)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_ctx": estimate_num_ctx(system_content, user_content),
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
        '  "decision": "apply" | "no apply",\n'
        '  "confidence": 0-100,\n'
        '  "fit_summary": "one short paragraph",\n'
        '  "strengths": ["short bullet"],\n'
        '  "concerns": ["short bullet, ONLY if genuinely material — [] if none"],\n'
        '  "recommended_next_step": "short instruction"\n'
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
    decision = str(result.get("decision", "")).strip().casefold()
    if decision not in {"apply", "no apply"}:
        decision = "no apply"

    confidence = result.get("confidence", 0)
    try:
        confidence = max(0, min(100, int(confidence)))
    except (TypeError, ValueError):
        confidence = 0

    return {
        "decision": decision,
        "confidence": confidence,
        "fit_summary": str(result.get("fit_summary", "")).strip(),
        "strengths": list_of_strings(result.get("strengths", [])),
        "concerns": list_of_strings(result.get("concerns", [])),
        "recommended_next_step": str(result.get("recommended_next_step", "")).strip(),
    }


def list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def fallback_evaluation(match: MatchResult, threshold: int, error: str | None = None) -> dict[str, Any]:
    decision = "apply" if match.score >= threshold else "no apply"
    result = {
        "decision": decision,
        "confidence": min(95, max(30, match.score)),
        "fit_summary": (
            "Fallback decision based on keyword scoring because the local LLM "
            "was not used or was unavailable."
        ),
        "strengths": match.matched_terms[:8],
        "concerns": match.missing_terms[:8],
        "recommended_next_step": "Review the job details manually before applying.",
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
