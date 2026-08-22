from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_bot.models import CandidateProfile, JobPosting
from job_bot.profile_data import profile_from_structured_data


ROOT = Path(__file__).resolve().parent.parent


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_settings(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or ROOT / "config" / "settings.json"
    return load_json(settings_path)


def load_profile(path: Path | None = None) -> CandidateProfile:
    profile_path = path or ROOT / "config" / "profile.json"
    data = load_json(profile_path)
    if "surname" in data or "experience" in data:
        return profile_from_structured_data(data)
    return CandidateProfile.from_dict(data)


def load_profile_context(path: Path | None = None) -> str:
    context_path = path or ROOT / "config" / "profile_context.md"
    if not context_path.exists():
        return ""
    return context_path.read_text(encoding="utf-8").strip()


def load_jobs(path: Path | None = None) -> list[JobPosting]:
    jobs_path = path or ROOT / "data" / "jobs.json"
    return [JobPosting.from_dict(item) for item in load_json(jobs_path)]


def project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return ROOT / path
