from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from job_bot.config import ROOT, load_json, load_profile, project_path
from job_bot.job_fetcher import HTMLTextOnly, clean_text, fetch_job_from_url, infer_requirements
from job_bot.ledger import already_processed_job_ids
from job_bot.matcher import score_job
from job_bot.models import CandidateProfile, JobPosting


ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"
USER_AGENT = "job-bot/1.0 (personal job search assistant; github.com; contact via profile)"
LOW_CONFIDENCE_TEXT_LENGTH = 200


def fetch_arbeitnow_page(page: int, timeout_seconds: int = 20) -> dict[str, Any]:
    request = Request(
        f"{ARBEITNOW_API_URL}?page={page}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not fetch Arbeitnow page {page}: {exc}") from exc


def job_posting_from_arbeitnow(listing: dict[str, Any]) -> JobPosting:
    url = str(listing.get("url", ""))
    title = str(listing.get("title", "")).strip()
    company = str(listing.get("company_name", "")).strip() or "Unknown Company"
    location = str(listing.get("location", "")).strip()
    if listing.get("remote") and "remote" not in location.casefold():
        location = f"{location}, Remote".strip(", ")

    description_html = str(listing.get("description", ""))
    text = clean_text(HTMLTextOnly.strip_tags(description_html))
    tags = [str(tag).strip() for tag in listing.get("tags", []) if str(tag).strip()]

    requirements = infer_requirements(text)
    for tag in tags:
        if tag not in requirements:
            requirements.append(tag)

    return JobPosting(
        id=hashlib.sha256(url.encode("utf-8")).hexdigest()[:16],
        title=title,
        company=company,
        location=location,
        url=url,
        description=text[:12000],
        requirements=requirements,
        description_confidence=(
            "low" if len(text.strip()) < LOW_CONFIDENCE_TEXT_LENGTH else "high"
        ),
    )


def iter_arbeitnow_candidates(
    max_pages: int,
    timeout_seconds: int = 20,
    request_delay_seconds: float = 0.5,
):
    """Yields JobPosting candidates from Arbeitnow's free public job board API,
    one page (~175 listings) at a time. Arbeitnow has no keyword search, so
    filtering for fit happens client-side via score_job."""
    for page in range(1, max_pages + 1):
        payload = fetch_arbeitnow_page(page, timeout_seconds=timeout_seconds)
        listings = payload.get("data", [])
        if not listings:
            return
        for listing in listings:
            yield job_posting_from_arbeitnow(listing)
        if not payload.get("links", {}).get("next"):
            return
        if page < max_pages:
            time.sleep(request_delay_seconds)


def resolve_path(path: Path | str) -> Path:
    return path if Path(path).is_absolute() else project_path(path)


def score_and_save_candidates(
    candidates,
    min_score: int,
    profile_path: Path | str,
    jobs_path: Path | str,
    ledger_path: Path | str,
    target_count: int | None = None,
) -> dict[str, Any]:
    """Shared plumbing for any candidate source: score each JobPosting against
    the profile, dedupe against what's already in jobs.json or the ledger,
    and append qualifying matches to jobs.json. `candidates` is any iterable
    of JobPosting — Arbeitnow pagination and a curated URL list both funnel
    through here so scoring/dedup/writing only exists once."""
    resolved_profile_path = resolve_path(profile_path)
    resolved_jobs_path = resolve_path(jobs_path)
    resolved_ledger_path = resolve_path(ledger_path)

    profile = load_profile(resolved_profile_path)
    existing_jobs = load_existing_jobs(resolved_jobs_path)
    existing_ids = {str(job["id"]) for job in existing_jobs}
    processed_ids = already_processed_job_ids(resolved_ledger_path)
    skip_ids = existing_ids | processed_ids

    matches: list[dict[str, Any]] = []
    scanned = 0

    for job in candidates:
        scanned += 1
        if job.id in skip_ids:
            continue
        skip_ids.add(job.id)

        match = score_job(profile, job)
        if match.score < min_score:
            continue

        matches.append({"job": job, "score": match.score, "reasons": match.reasons})
        if target_count is not None and len(matches) >= target_count:
            break

    matches.sort(key=lambda entry: entry["score"], reverse=True)

    updated_jobs = existing_jobs + [job_to_dict(entry["job"]) for entry in matches]
    write_jobs(resolved_jobs_path, updated_jobs)

    return {
        "scanned": scanned,
        "matches": matches,
        "jobs_path": resolved_jobs_path,
        "total_jobs_in_file": len(updated_jobs),
    }


def search_and_save_jobs(
    target_count: int = 20,
    min_score: int = 60,
    max_pages: int = 10,
    profile_path: Path | str = "config/profile.json",
    jobs_path: Path | str = "data/jobs.json",
    ledger_path: Path | str = "data/applications_ledger.jsonl",
) -> dict[str, Any]:
    return score_and_save_candidates(
        iter_arbeitnow_candidates(max_pages=max_pages),
        min_score=min_score,
        profile_path=profile_path,
        jobs_path=jobs_path,
        ledger_path=ledger_path,
        target_count=target_count,
    )


def iter_url_candidates(urls: list[str], timeout_seconds: int = 20):
    """Yields JobPosting candidates fetched directly from a curated list of
    real job posting URLs (e.g. found via interactive web search), reusing
    the same JSON-LD-aware fetcher as the single-URL evaluator. A page that
    fails to fetch is skipped, not fatal to the rest of the batch."""
    for url in urls:
        try:
            yield fetch_job_from_url(url, timeout_seconds=timeout_seconds)
        except RuntimeError:
            continue


def save_jobs_from_urls(
    urls: list[str],
    min_score: int = 60,
    profile_path: Path | str = "config/profile.json",
    jobs_path: Path | str = "data/jobs.json",
    ledger_path: Path | str = "data/applications_ledger.jsonl",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    return score_and_save_candidates(
        iter_url_candidates(urls, timeout_seconds=timeout_seconds),
        min_score=min_score,
        profile_path=profile_path,
        jobs_path=jobs_path,
        ledger_path=ledger_path,
    )


def load_existing_jobs(jobs_path: Path) -> list[dict[str, Any]]:
    if not jobs_path.exists():
        return []
    return load_json(jobs_path)


def job_to_dict(job: JobPosting) -> dict[str, Any]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description": job.description,
        "requirements": job.requirements,
        "description_confidence": job.description_confidence,
    }


def write_jobs(jobs_path: Path, jobs: list[dict[str, Any]]) -> None:
    jobs_path.parent.mkdir(parents=True, exist_ok=True)
    jobs_path.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
