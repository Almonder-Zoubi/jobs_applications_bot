from __future__ import annotations

import argparse
import json
from pathlib import Path

from job_bot.config import ROOT, load_profile
from job_bot.job_fetcher import fetch_job_from_url
from job_bot.matcher import score_job


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a job URL and decide whether it looks suitable."
    )
    parser.add_argument("url", help="Job posting URL to evaluate.")
    parser.add_argument(
        "--profile",
        default="config/profile.json",
        help="Path to the candidate JSON profile.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum score considered suitable.",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path

    profile = load_profile(profile_path)
    job = fetch_job_from_url(args.url)
    match = score_job(profile, job)
    suitable = match.score >= args.min_score

    print(json.dumps(
        {
            "suitable": suitable,
            "score": match.score,
            "threshold": args.min_score,
            "job": {
                "title": job.title,
                "company": job.company,
                "url": job.url,
            },
            "matched_terms": match.matched_terms,
            "missing_or_gap_terms": match.missing_terms,
            "reasons": match.reasons,
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
