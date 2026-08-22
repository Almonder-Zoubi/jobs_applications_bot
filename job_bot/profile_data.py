from __future__ import annotations

from typing import Any

from job_bot.models import CandidateProfile


DEFAULT_INTERESTED_ROLES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Data Engineer",
    "Data Scientist",
    "Python Developer",
    "Backend Developer",
    "Software Engineer",
    "Research Engineer",
]

DEFAULT_AVOID_ROLES = [
    "Unpaid Internship",
    "Sales",
    "Senior Manager",
]

DEFAULT_LOCATIONS = [
    "Germany",
    "Berlin",
    "Brandenburg",
    "Remote",
    "Hybrid",
]


def profile_from_structured_data(data: dict[str, Any]) -> CandidateProfile:
    name = " ".join(
        part
        for part in [str(data.get("name", "")).strip(), str(data.get("surname", "")).strip()]
        if part
    )
    skills = unique_preserving_order(
        flatten_skills(data.get("skills", [])) + flatten_flat_list(data.get("soft skills", []))
    )
    background = unique_preserving_order(
        flatten_experience(data.get("experience", []))
        + flatten_education(data.get("education", []))
        + flatten_projects(data.get("projects", []))
        + flatten_flat_list(data.get("languages", {}))
    )
    profile_summary = str(data.get("profile_summary", "")).strip()

    return CandidateProfile(
        name=name or "Candidate",
        email=str(data.get("email", "")),
        phone=str(data.get("phone_number", "")),
        location=str(data.get("address", "")),
        cv_summary=profile_summary or build_summary(skills, background),
        background=background,
        certificates=flatten_flat_list(data.get("certificates", [])),
        skills=skills,
        interested_roles=flatten_flat_list(
            data.get("interested_roles", DEFAULT_INTERESTED_ROLES)
        ),
        avoid_roles=flatten_flat_list(data.get("avoid_roles", DEFAULT_AVOID_ROLES)),
        preferred_locations=flatten_locations(
            data.get("preferred_locations", DEFAULT_LOCATIONS)
        ),
        work_authorization=str(
            data.get("work_authorization", "Authorized to work in Germany")
        ),
        salary_expectation=format_salary(data),
        resume_path=str(data.get("resume_path", "files/CV_Almonder_Zoubi.pdf")),
        cover_letter_style=str(
            data.get(
                "cover_letter_style",
                "Professional, concise, confident, and specific.",
            )
        ),
    )


def flatten_skills(raw_skills: Any) -> list[str]:
    flattened: list[str] = []
    if not isinstance(raw_skills, list):
        return flattened

    for item in raw_skills:
        if not isinstance(item, dict):
            continue
        for values in item.values():
            if isinstance(values, list):
                flattened.extend(str(value) for value in values)

    return unique_preserving_order(flattened)


def flatten_experience(raw_experience: Any) -> list[str]:
    flattened: list[str] = []
    if not isinstance(raw_experience, list):
        return flattened

    for entry in raw_experience:
        if not isinstance(entry, dict):
            continue
        company = str(entry.get("company", "")).strip()
        position = str(entry.get("position", "")).strip()
        if company or position:
            flattened.append(f"{position} at {company}".strip())
        flattened.extend(str(item) for item in entry.get("responsibilities", []))
        flattened.extend(str(item) for item in entry.get("achievements", []))

    return unique_preserving_order(flattened)


def flatten_education(raw_education: Any) -> list[str]:
    flattened: list[str] = []
    if not isinstance(raw_education, list):
        return flattened

    for entry in raw_education:
        if not isinstance(entry, dict):
            continue
        degree = str(entry.get("degree", "")).strip()
        major = str(entry.get("major", "")).strip()
        institution = str(entry.get("institution", "")).strip()
        pieces = [
            piece
            for piece in [
                degree,
                f"in {major}" if major else "",
                f"at {institution}" if institution else "",
            ]
            if piece
        ]
        if pieces:
            flattened.append(" ".join(pieces))
        flattened.extend(str(item) for item in entry.get("relevant_courses", []))

    return unique_preserving_order(flattened)


def flatten_projects(raw_projects: Any) -> list[str]:
    flattened: list[str] = []
    if isinstance(raw_projects, dict):
        for values in raw_projects.values():
            if isinstance(values, list):
                flattened.extend(str(value) for value in values)
    elif isinstance(raw_projects, list):
        flattened.extend(str(value) for value in raw_projects)

    return unique_preserving_order(flattened)


def flatten_locations(raw_locations: Any) -> list[str]:
    flattened: list[str] = []
    if isinstance(raw_locations, dict):
        for key, values in raw_locations.items():
            flattened.append(str(key))
            if isinstance(values, list):
                flattened.extend(str(value) for value in values)
    elif isinstance(raw_locations, list):
        flattened.extend(str(value) for value in raw_locations)

    return unique_preserving_order(flattened)


def flatten_flat_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return unique_preserving_order([str(item) for item in value])
    if isinstance(value, dict):
        return unique_preserving_order([f"{key}: {val}" for key, val in value.items()])
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def format_salary(data: dict[str, Any]) -> str:
    raw = data.get("salary_expectation")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()

    structured = data.get("salary_expectations")
    if isinstance(structured, dict) and structured.get("amount"):
        amount = structured["amount"]
        currency = str(structured.get("currency", "")).strip()
        try:
            amount_text = f"{int(amount):,}"
        except (TypeError, ValueError):
            amount_text = str(amount)
        return f"{amount_text} {currency}".strip()

    return "Open to discussion"


def build_summary(skills: list[str], background: list[str]) -> str:
    top_skills = ", ".join(skills[:10])
    top_background = " ".join(background[:2])
    return f"Technical profile with skills in {top_skills}. {top_background}".strip()


def unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result
