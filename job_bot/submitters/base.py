from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from job_bot.models import ApplicationPacket


@dataclass(frozen=True)
class SubmissionResult:
    status: str
    detail: str
    confirmation_url: str | None = None


class Submitter(Protocol):
    name: str

    def can_handle(self, packet: ApplicationPacket) -> bool:
        """Return True when this submitter supports the job posting URL."""

    def submit(self, packet: ApplicationPacket) -> SubmissionResult:
        """Submit or stage an application packet."""

