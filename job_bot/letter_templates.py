from __future__ import annotations

from pathlib import Path
from typing import Any

from job_bot.config import ROOT, load_json
from job_bot.models import JobPosting


def load_motivation_templates(path: Path | None = None) -> dict[str, Any]:
    templates_path = path or ROOT / "config" / "motivation_templates.json"
    if not templates_path.exists():
        return {}
    return load_json(templates_path)


def select_letter_template(
    job: JobPosting, templates: dict[str, Any]
) -> dict[str, Any] | None:
    haystack = f"{job.title} {' '.join(job.requirements)}".casefold()

    best_category: str | None = None
    best_hits = 0
    for category, template in templates.items():
        target_roles = template.get("target_roles", [])
        hits = sum(1 for role in target_roles if str(role).casefold() in haystack)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    if best_category is None:
        return None
    return {"category": best_category, **templates[best_category]}
