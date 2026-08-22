from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from job_bot.models import LedgerEntry


def read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def already_processed_job_ids(path: Path) -> set[str]:
    return {entry["job_id"] for entry in read_entries(path)}


def count_for_day(path: Path, day: date) -> int:
    return sum(1 for entry in read_entries(path) if entry["prepared_on"] == day.isoformat())


def append_entry(path: Path, entry: LedgerEntry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(entry)
    data["prepared_on"] = entry.prepared_on.isoformat()
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False) + "\n")

