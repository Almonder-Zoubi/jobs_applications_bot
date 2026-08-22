import tempfile
import unittest
from pathlib import Path

from job_bot.config import load_profile, load_profile_context


class LoadProfileContextTest(unittest.TestCase):
    def test_returns_empty_string_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "profile_context.md"

            self.assertEqual(load_profile_context(missing_path), "")

    def test_reads_and_strips_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            context_path = Path(tmpdir) / "profile_context.md"
            context_path.write_text(
                "\n  # Candidate Context\n\nSome guidance.\n\n", encoding="utf-8"
            )

            self.assertEqual(
                load_profile_context(context_path),
                "# Candidate Context\n\nSome guidance.",
            )


class LoadProfileTest(unittest.TestCase):
    def test_detects_structured_cv_profile_by_experience_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile.json"
            profile_path.write_text(
                """
                {
                    "name": "Test",
                    "surname": "Candidate",
                    "skills": [{"tools": ["Docker"]}],
                    "experience": [
                        {"company": "Example", "position": "Engineer",
                         "responsibilities": ["Built things"]}
                    ]
                }
                """,
                encoding="utf-8",
            )

            profile = load_profile(profile_path)

            self.assertEqual(profile.name, "Test Candidate")
            self.assertIn("Built things", profile.background)

    def test_uses_flat_schema_when_no_cv_markers_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile.json"
            profile_path.write_text(
                """
                {
                    "name": "Test Candidate",
                    "email": "test@example.com",
                    "phone": "+49 000",
                    "location": "Berlin",
                    "cv_summary": "Summary",
                    "background": ["Did things"],
                    "certificates": [],
                    "skills": ["Python"],
                    "interested_roles": ["Python Developer"],
                    "avoid_roles": [],
                    "preferred_locations": ["Berlin"],
                    "work_authorization": "Authorized",
                    "salary_expectation": "Open",
                    "resume_path": "data/resume.pdf",
                    "cover_letter_style": "Professional"
                }
                """,
                encoding="utf-8",
            )

            profile = load_profile(profile_path)

            self.assertEqual(profile.name, "Test Candidate")
            self.assertEqual(profile.background, ["Did things"])


if __name__ == "__main__":
    unittest.main()
