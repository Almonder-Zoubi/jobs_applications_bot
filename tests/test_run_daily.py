import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from job_bot.run_daily import run_daily


PROFILE = {
    "name": "Test Candidate",
    "email": "test@example.com",
    "phone": "+49 000",
    "location": "Berlin",
    "cv_summary": "Python automation engineer",
    "background": ["Built Python automation"],
    "certificates": [],
    "skills": ["Python", "REST APIs", "SQL"],
    "interested_roles": ["Python Developer"],
    "avoid_roles": ["Unpaid Internship"],
    "preferred_locations": ["Berlin", "Remote"],
    "work_authorization": "Authorized to work in Germany",
    "salary_expectation": "Open",
    "resume_path": "data/resume.pdf",
    "cover_letter_style": "Professional",
}

GOOD_JOB = {
    "id": "good-job-1",
    "title": "Python Developer",
    "company": "Example GmbH",
    "location": "Berlin",
    "url": "https://example.com/jobs/1",
    "description": "Build backend services with Python and REST APIs.",
    "requirements": ["Python", "REST APIs", "SQL"],
}

WEAK_JOB = {
    "id": "weak-job-2",
    "title": "Unpaid Internship",
    "company": "Example GmbH",
    "location": "Berlin",
    "url": "https://example.com/jobs/2",
    "description": "Unpaid internship role.",
    "requirements": ["Python"],
}

SENIOR_LEANING_JOB = {
    "id": "senior-job-3",
    "title": "Python Developer",
    "company": "Example GmbH",
    "location": "Berlin",
    "url": "https://example.com/jobs/3",
    "description": (
        "Build backend services with Python and REST APIs. Requires 5+ years "
        "of experience and a senior mindset."
    ),
    "requirements": ["Python", "REST APIs", "SQL"],
}


class RunDailyTest(unittest.TestCase):
    def test_prepares_letters_and_writes_to_apply_summary_for_no_llm_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            (tmp / "jobs.json").write_text(
                json.dumps([GOOD_JOB, WEAK_JOB]), encoding="utf-8"
            )

            settings = {
                "daily_limit": 20,
                "minimum_match_score": 60,
                "output_dir": str(tmp / "applications"),
                "to_apply_dir": str(tmp / "out"),
                "ledger_path": str(tmp / "ledger.jsonl"),
                "jobs_path": str(tmp / "jobs.json"),
                "profile_path": str(tmp / "profile.json"),
                "profile_context_path": str(tmp / "missing_context.md"),
                "use_llm": True,
            }

            result = run_daily(settings, use_llm_override=False)

            self.assertEqual(len(result["prepared"]), 1)
            prepared_job, _, output_dir = result["prepared"][0]
            self.assertEqual(prepared_job.id, "good-job-1")
            self.assertTrue((output_dir / "motivation_letter.txt").exists())

            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["skipped"][0][0].id, "weak-job-2")

            to_apply_path = result["to_apply_path"]
            self.assertEqual(
                to_apply_path.name, f"to_apply_{date.today().isoformat()}.json"
            )
            to_apply_entries = json.loads(to_apply_path.read_text(encoding="utf-8"))
            self.assertEqual(len(to_apply_entries), 1)
            self.assertEqual(to_apply_entries[0]["job_id"], "good-job-1")
            self.assertEqual(to_apply_entries[0]["decision"], "apply")
            self.assertIn("generated_letter_path", to_apply_entries[0])

    def test_flagged_matches_go_to_preview_first_not_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            (tmp / "jobs.json").write_text(
                json.dumps([SENIOR_LEANING_JOB]), encoding="utf-8"
            )

            settings = {
                "daily_limit": 20,
                "minimum_match_score": 50,
                "output_dir": str(tmp / "applications"),
                "to_apply_dir": str(tmp / "out"),
                "ledger_path": str(tmp / "ledger.jsonl"),
                "jobs_path": str(tmp / "jobs.json"),
                "profile_path": str(tmp / "profile.json"),
                "profile_context_path": str(tmp / "missing_context.md"),
                "use_llm": True,
            }

            result = run_daily(settings, use_llm_override=False)

            self.assertEqual(len(result["prepared"]), 1)
            self.assertEqual(len(result["to_apply"]), 0)
            self.assertEqual(len(result["to_preview_first"]), 1)

            flagged_entry = result["to_preview_first"][0]
            self.assertEqual(flagged_entry["job_id"], "senior-job-3")
            self.assertTrue(
                any("seniority" in reason for reason in flagged_entry["review_reasons"])
            )

            preview_path = result["to_preview_first_path"]
            self.assertEqual(
                preview_path.name, f"to_preview_first_{date.today().isoformat()}.json"
            )
            preview_entries = json.loads(preview_path.read_text(encoding="utf-8"))
            self.assertEqual(len(preview_entries), 1)

            to_apply_entries = json.loads(
                result["to_apply_path"].read_text(encoding="utf-8")
            )
            self.assertEqual(to_apply_entries, [])

    def test_already_processed_jobs_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            (tmp / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            (tmp / "jobs.json").write_text(json.dumps([GOOD_JOB]), encoding="utf-8")
            ledger_path = tmp / "ledger.jsonl"
            ledger_path.write_text(
                json.dumps(
                    {
                        "job_id": "good-job-1",
                        "company": "Example GmbH",
                        "title": "Python Developer",
                        "url": GOOD_JOB["url"],
                        "status": "prepared",
                        "score": 90,
                        "prepared_on": date.today().isoformat(),
                        "output_path": "somewhere",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            settings = {
                "daily_limit": 20,
                "minimum_match_score": 60,
                "output_dir": str(tmp / "applications"),
                "to_apply_dir": str(tmp / "out"),
                "ledger_path": str(ledger_path),
                "jobs_path": str(tmp / "jobs.json"),
                "profile_path": str(tmp / "profile.json"),
                "profile_context_path": str(tmp / "missing_context.md"),
                "use_llm": True,
            }

            result = run_daily(settings, use_llm_override=False)

            self.assertEqual(len(result["prepared"]), 0)
            self.assertEqual(len(result["skipped"]), 1)
            self.assertEqual(result["skipped"][0][1], "already processed")


if __name__ == "__main__":
    unittest.main()
