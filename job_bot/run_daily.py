from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from job_bot.config import ROOT, load_jobs, load_profile, load_profile_context, load_settings, project_path
from job_bot.evaluate import evaluate_job
from job_bot.ledger import already_processed_job_ids, append_entry, count_for_day
from job_bot.letter import generate_motivation_letter
from job_bot.letter_templates import load_motivation_templates, select_letter_template
from job_bot.matcher import score_job
from job_bot.models import ApplicationPacket, JobPosting, LedgerEntry
from job_bot.ollama_client import DEFAULT_MODEL, DEFAULT_OLLAMA_URL


def write_packet(packet: ApplicationPacket, output_root: Path) -> Path:
    day_dir = output_root / packet.prepared_at.date().isoformat()
    safe_company = slug(packet.job.company)
    safe_title = slug(packet.job.title)
    output_dir = day_dir / f"{safe_company}-{safe_title}-{packet.job.id}"
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "motivation_letter.txt").write_text(
        packet.motivation_letter, encoding="utf-8"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "job": asdict(packet.job),
                "match": asdict(packet.match),
                "prepared_at": packet.prepared_at.isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output_dir


def slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "job"


def build_to_apply_entry(
    job: JobPosting,
    evaluation: dict[str, Any],
    letter_path: Path,
    template: dict[str, Any] | None,
    review_reasons: list[str],
) -> dict[str, Any]:
    llm_evaluation = evaluation["llm"]["evaluation"]
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "url": job.url,
        "decision": evaluation["decision"],
        "keyword_score": evaluation["score"],
        "keyword_threshold": evaluation["threshold"],
        "llm_confidence": llm_evaluation.get("confidence"),
        "fit_summary": llm_evaluation.get("fit_summary", ""),
        "strengths": llm_evaluation.get("strengths") or evaluation["matched_terms"],
        "missing_or_concerns": llm_evaluation.get("concerns") or evaluation["missing_or_gap_terms"],
        "description_confidence": job.description_confidence,
        "review_reasons": review_reasons,
        "suggested_letter_template": template,
        "generated_letter_path": str(letter_path),
        "evaluated_at": evaluation["evaluated_at"],
    }


def needs_manual_review(job: JobPosting, evaluation: dict[str, Any]) -> tuple[bool, list[str]]:
    """A job can pass both stages and still be worth a second look before
    actually applying — the LLM raised a concern, the deterministic matcher
    flagged a seniority/experience-level signal, or the fetched description
    was too thin to fully trust the evaluation. Route those to
    to_preview_first instead of to_apply so a clean pass in to_apply really
    means "nothing raised a flag", not just "score cleared the bar"."""
    reasons: list[str] = []
    if evaluation["llm"]["evaluation"].get("concerns"):
        reasons.append("LLM raised a concern")
    if any("Seniority" in reason for reason in evaluation["reasons"]):
        reasons.append("seniority/experience-level signal detected in description")
    if job.description_confidence == "low":
        reasons.append("job description text was too thin to fully trust")
    return bool(reasons), reasons


def write_json_summary(entries: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_daily(
    settings: dict[str, Any],
    limit_override: int | None = None,
    min_score_override: int | None = None,
    use_llm_override: bool | None = None,
) -> dict[str, Any]:
    profile_path = project_path(settings["profile_path"])
    profile_context_path = project_path(
        settings.get("profile_context_path", "config/profile_context.md")
    )
    profile = load_profile(profile_path)
    profile_context = load_profile_context(profile_context_path)
    jobs = load_jobs(project_path(settings["jobs_path"]))
    templates = load_motivation_templates()

    daily_limit = limit_override if limit_override is not None else int(settings["daily_limit"])
    minimum_score = (
        min_score_override
        if min_score_override is not None
        else int(settings["minimum_match_score"])
    )
    use_llm = (
        bool(settings.get("use_llm", True)) if use_llm_override is None else use_llm_override
    )
    model = settings.get("model", DEFAULT_MODEL)
    ollama_url = settings.get("ollama_url", DEFAULT_OLLAMA_URL)
    ollama_timeout = int(settings.get("ollama_timeout", 120))
    ledger_path = project_path(settings["ledger_path"])
    output_root = project_path(settings["output_dir"])
    to_apply_dir = project_path(settings.get("to_apply_dir", "out"))

    today = date.today()
    remaining = max(0, daily_limit - count_for_day(ledger_path, today))
    processed_ids = already_processed_job_ids(ledger_path)

    prepared = []
    skipped = []
    to_apply: list[dict[str, Any]] = []
    to_preview_first: list[dict[str, Any]] = []

    for job in jobs:
        if remaining <= 0:
            break
        if job.id in processed_ids:
            skipped.append((job, "already processed"))
            continue

        evaluation = evaluate_job(
            profile=profile,
            job=job,
            profile_context=profile_context,
            min_score=minimum_score,
            use_llm=use_llm,
            model=model,
            ollama_url=ollama_url,
            ollama_timeout=ollama_timeout,
            profile_source=str(profile_path),
            profile_context_source=str(profile_context_path),
        )

        if evaluation["decision"] != "apply":
            llm_decision = evaluation["llm"]["evaluation"]["decision"]
            skipped.append(
                (
                    job,
                    f"decision=no apply (keyword score {evaluation['score']}, "
                    f"llm recommendation {llm_decision})",
                )
            )
            continue

        match = score_job(profile, job)
        letter = generate_motivation_letter(profile, job, match)
        packet = ApplicationPacket(
            job=job,
            match=match,
            motivation_letter=letter,
            prepared_at=datetime.now(),
        )
        output_dir = write_packet(packet, output_root)
        append_entry(
            ledger_path,
            LedgerEntry(
                job_id=job.id,
                company=job.company,
                title=job.title,
                url=job.url,
                status="prepared",
                score=match.score,
                prepared_on=today,
                output_path=str(output_dir),
            ),
        )
        prepared.append((job, match, output_dir))
        remaining -= 1

        template = select_letter_template(job, templates)
        review_flagged, review_reasons = needs_manual_review(job, evaluation)
        entry = build_to_apply_entry(
            job, evaluation, output_dir / "motivation_letter.txt", template, review_reasons
        )
        if review_flagged:
            to_preview_first.append(entry)
        else:
            to_apply.append(entry)

    to_apply_path = write_json_summary(to_apply, to_apply_dir / f"to_apply_{today.isoformat()}.json")
    to_preview_path = write_json_summary(
        to_preview_first, to_apply_dir / f"to_preview_first_{today.isoformat()}.json"
    )

    return {
        "prepared": prepared,
        "skipped": skipped,
        "to_apply": to_apply,
        "to_apply_path": to_apply_path,
        "to_preview_first": to_preview_first,
        "to_preview_first_path": to_preview_path,
        "daily_limit": daily_limit,
        "remaining": remaining,
    }


def run() -> int:
    parser = argparse.ArgumentParser(description="Prepare daily job applications.")
    parser.add_argument("--limit", type=int, help="Override daily application limit.")
    parser.add_argument(
        "--min-score", type=int, help="Override minimum match score, 0-100."
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the LLM verification stage and use keyword-score fallback only.",
    )
    args = parser.parse_args()

    settings = load_settings()
    result = run_daily(
        settings,
        limit_override=args.limit,
        min_score_override=args.min_score,
        use_llm_override=(False if args.no_llm else None),
    )

    prepared = result["prepared"]
    skipped = result["skipped"]

    print(f"Prepared {len(prepared)} application(s).")
    print(f"Daily limit: {result['daily_limit']}. Remaining today: {result['remaining']}.")
    for job, match, output_dir in prepared:
        print(f"- {job.company} | {job.title} | score {match.score} | {output_dir}")
    if skipped:
        print(f"Skipped {len(skipped)} job(s).")
        for job, reason in skipped[:10]:
            print(f"- {job.company} | {job.title} | {reason}")
    print(f"To-apply summary: {result['to_apply_path']} ({len(result['to_apply'])} job(s)).")
    print(
        f"To-preview-first summary: {result['to_preview_first_path']} "
        f"({len(result['to_preview_first'])} job(s) that passed but need a manual look)."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(run())
