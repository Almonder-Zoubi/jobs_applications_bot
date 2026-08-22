#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.job_search import search_and_save_jobs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Search Arbeitnow's public job board API for postings matching "
            "the candidate profile's keyword score, and append matches to "
            "data/jobs.json. Does not call the LLM or write letters — run "
            "job_bot.run_daily afterward for the full two-stage evaluation."
        )
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=20,
        help="Stop once this many new matching jobs are found. Defaults to 20.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum keyword score (job_bot.matcher.score_job) to count as a match.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum Arbeitnow API pages (~175 listings each) to scan.",
    )
    parser.add_argument("--profile", default="config/profile.json")
    parser.add_argument("--jobs-path", default="data/jobs.json")
    parser.add_argument("--ledger-path", default="data/applications_ledger.jsonl")
    args = parser.parse_args()

    result = search_and_save_jobs(
        target_count=args.target_count,
        min_score=args.min_score,
        max_pages=args.max_pages,
        profile_path=args.profile,
        jobs_path=args.jobs_path,
        ledger_path=args.ledger_path,
    )

    print(f"Scanned {result['scanned']} listing(s).")
    print(f"Found {len(result['matches'])} new match(es) at or above score {args.min_score}:")
    for entry in result["matches"]:
        job = entry["job"]
        print(f"- {job.company} | {job.title} | score {entry['score']} | {job.url}")
    print(f"Wrote {result['jobs_path']} ({result['total_jobs_in_file']} job(s) total).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
