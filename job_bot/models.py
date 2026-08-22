from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    email: str
    phone: str
    location: str
    cv_summary: str
    background: list[str]
    certificates: list[str]
    skills: list[str]
    interested_roles: list[str]
    avoid_roles: list[str]
    preferred_locations: list[str]
    work_authorization: str
    salary_expectation: str
    resume_path: str
    cover_letter_style: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateProfile:
        return cls(**data)


@dataclass(frozen=True)
class JobPosting:
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    requirements: list[str] = field(default_factory=list)
    description_confidence: str = "high"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobPosting:
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            company=str(data["company"]),
            location=str(data.get("location", "")),
            url=str(data.get("url", "")),
            description=str(data.get("description", "")),
            requirements=[str(item) for item in data.get("requirements", [])],
            description_confidence=str(data.get("description_confidence", "high")),
        )


@dataclass(frozen=True)
class MatchResult:
    score: int
    matched_terms: list[str]
    missing_terms: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class ApplicationPacket:
    job: JobPosting
    match: MatchResult
    motivation_letter: str
    prepared_at: datetime


@dataclass(frozen=True)
class LedgerEntry:
    job_id: str
    company: str
    title: str
    url: str
    status: str
    score: int
    prepared_on: date
    output_path: str

