#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.evaluate import evaluate_job_url, write_evaluation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate one real job URL against config/profile.json only."
    )
    parser.add_argument("url", help="Job posting URL to evaluate.")
    parser.add_argument(
        "--profile",
        default="config/profile.json",
        help="Candidate profile JSON path. Defaults to config/profile.json.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum score considered suitable. Defaults to 60.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Fetch timeout in seconds. Defaults to 20.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Ollama and use keyword-score fallback.",
    )
    args = parser.parse_args()

    result = evaluate_job_url(
        url=args.url,
        profile_path=args.profile,
        min_score=args.min_score,
        fetch_timeout=args.timeout,
        use_llm=not args.no_llm,
    )
    output_path = write_evaluation(result, args.output)
    result["output_path"] = str(output_path)
    role_description = result.pop("role_description_full", None)
    if role_description is not None:
        result["role_description_full"] = role_description
    write_evaluation(result, output_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
