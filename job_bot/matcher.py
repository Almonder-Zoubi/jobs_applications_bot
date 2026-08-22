from __future__ import annotations

import re

from job_bot.models import CandidateProfile, JobPosting, MatchResult


WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]*")
SENIORITY_TITLE_TERMS = [
    "senior",
    "staff",
    "principal",
    "lead",
    "head of",
    "director",
    "vp",
    "vice president",
]
EXPERIENCE_YEARS_RE = re.compile(
    r"(\d{1,2})\+?\s*(?:[-–]|to)?\s*\d{0,2}\+?\s*years?", re.IGNORECASE
)
MIN_SENIOR_YEARS = 4
ALIASES = {
    "nlp": ["natural language processing"],
    "natural language processing": ["nlp"],
    "sql": ["mysql", "postgresql", "database", "databases"],
    "postgresql": ["sql"],
    "mysql": ["sql"],
    "rag": ["retrieval-augmented generation", "retreival-augmented generation"],
    "retreival-augmented generation (rag)": ["rag", "retrieval-augmented generation"],
}


def normalize(text: str) -> str:
    return text.casefold()


def tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in WORD_RE.finditer(text)}


def phrase_hits(phrases: list[str], haystack: str) -> list[str]:
    return [phrase for phrase in phrases if term_matches_text(phrase, haystack)]


def contains_normalized(normalized_value: str, normalized_haystack: str) -> bool:
    """Word-boundary match for short alnum strings (e.g. "sql", "rag"), plain
    substring otherwise. A plain substring check is unsafe at this length —
    "rag" is a substring of "paragraph" — but a hyphen (as in "SQL-backed")
    is still a word boundary for regex \\b, so this still catches real
    hyphenated mentions."""
    if normalized_value.isalnum() and len(normalized_value) <= 3:
        return re.search(rf"\b{re.escape(normalized_value)}\b", normalized_haystack) is not None
    return normalized_value in normalized_haystack


def term_matches_text(term: str, haystack: str) -> bool:
    normalized_haystack = normalize(haystack)
    normalized_term = normalize(term)
    if contains_normalized(normalized_term, normalized_haystack):
        return True
    return any(
        contains_normalized(normalize(alias), normalized_haystack)
        for alias in ALIASES.get(normalized_term, [])
    )


def term_matches_tokens(term: str, haystack_tokens: set[str], haystack_text: str) -> bool:
    if term_matches_text(term, haystack_text):
        return True

    term_token_set = tokens(term)
    if not term_token_set:
        return False
    if len(term_token_set) == 1:
        return next(iter(term_token_set)) in haystack_tokens
    return term_token_set.issubset(haystack_tokens)


def detect_seniority_signals(description: str) -> list[str]:
    """Scan the full job description (not just the title) for seniority
    titles and years-of-experience requirements. This is a soft signal, not
    a hard veto: body text can mention "senior" in passing (e.g. "you'll be
    mentored by senior engineers") without the role itself being senior, so
    a blunt veto here would produce false rejections."""
    folded = normalize(description)
    signals: list[str] = []
    for term in SENIORITY_TITLE_TERMS:
        if term in folded:
            signals.append(f'mentions "{term}"')
    for match in EXPERIENCE_YEARS_RE.finditer(description):
        if int(match.group(1)) >= MIN_SENIOR_YEARS:
            signals.append(match.group(0).strip())
    return list(dict.fromkeys(signals))


def score_job(profile: CandidateProfile, job: JobPosting) -> MatchResult:
    job_text = " ".join(
        [job.title, job.company, job.location, job.description, *job.requirements]
    )
    title_and_requirements_text = " ".join([job.title, *job.requirements])
    job_tokens = tokens(job_text)

    avoid_hits = phrase_hits(profile.avoid_roles, title_and_requirements_text)
    if avoid_hits:
        return MatchResult(
            score=0,
            matched_terms=[],
            missing_terms=avoid_hits,
            reasons=[f"Avoided role matched: {', '.join(avoid_hits)}"],
        )

    skill_hits = [
        skill
        for skill in profile.skills
        if term_matches_tokens(skill, job_tokens, job_text)
    ]
    role_hits = phrase_hits(profile.interested_roles, job.title)
    location_hits = phrase_hits(profile.preferred_locations, job.location)
    certificate_hits = phrase_hits(profile.certificates, job_text)

    requirement_text = " ".join(job.requirements)
    profile_text = " ".join(profile.skills + profile.background)
    profile_tokens = tokens(profile_text)
    missing_requirements = [
        requirement
        for requirement in job.requirements
        if not term_matches_tokens(requirement, profile_tokens, profile_text)
    ]
    seniority_signals = detect_seniority_signals(job.description)

    score = 20
    score += min(35, len(skill_hits) * 7)
    score += min(20, len(role_hits) * 20)
    score += min(15, len(location_hits) * 15)
    score += min(10, len(certificate_hits) * 5)
    score -= min(20, len(missing_requirements) * 5)
    score -= min(25, len(seniority_signals) * 10)
    score = max(0, min(100, score))

    reasons = []
    if skill_hits:
        reasons.append(f"Matched skills: {', '.join(skill_hits)}")
    if role_hits:
        reasons.append(f"Interested role match: {', '.join(role_hits)}")
    if location_hits:
        reasons.append(f"Preferred location match: {', '.join(location_hits)}")
    if certificate_hits:
        reasons.append(f"Certificate match: {', '.join(certificate_hits)}")
    if missing_requirements:
        reasons.append(f"Potential gaps: {', '.join(missing_requirements)}")
    if seniority_signals:
        reasons.append(
            f"Seniority/experience-level signals in description: {', '.join(seniority_signals)}"
        )
    if not reasons:
        reasons.append("Weak keyword match; review manually.")

    matched_terms = skill_hits + role_hits + location_hits + certificate_hits
    return MatchResult(
        score=score,
        matched_terms=matched_terms,
        missing_terms=missing_requirements,
        reasons=reasons,
    )
