#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from job_bot.evaluate import evaluate_job_url, write_evaluation
from job_bot.ollama_client import DEFAULT_MODEL, DEFAULT_OLLAMA_URL


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate one job URL with local Ollama and export JSON."
    )
    parser.add_argument("--url", required=True, help="Job posting URL to evaluate.")
    parser.add_argument(
        "--profile",
        default="config/profile.json",
        help="Candidate profile JSON path. Defaults to config/profile.json.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum keyword score considered suitable before LLM review.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model name. Defaults to gemma3:12b.",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Ollama server URL. Defaults to http://localhost:11434.",
    )
    parser.add_argument(
        "--output",
        help="Optional JSON output path. Defaults to out/evaluations/<timestamp>-<job>.json.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip Ollama and use keyword-score fallback. Useful for smoke tests.",
    )
    args = parser.parse_args()

    result = evaluate_job_url(
        url=args.url,
        profile_path=args.profile,
        min_score=args.min_score,
        use_llm=not args.no_llm,
        model=args.model,
        ollama_url=args.ollama_url,
    )
    output_path = write_evaluation(result, args.output)
    result["output_path"] = str(output_path)
    move_role_description_to_bottom(result)
    write_evaluation(result, output_path)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def move_role_description_to_bottom(result: dict) -> None:
    role_description = result.pop("role_description_full", None)
    if role_description is not None:
        result["role_description_full"] = role_description


if __name__ == "__main__":
    raise SystemExit(main())
