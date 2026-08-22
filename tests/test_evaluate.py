import unittest
from unittest.mock import patch

from job_bot.evaluate import evaluate_job
from job_bot.models import CandidateProfile, JobPosting


def profile() -> CandidateProfile:
    return CandidateProfile(
        name="Test User",
        email="test@example.com",
        phone="+49 000",
        location="Berlin",
        cv_summary="Python automation engineer",
        background=["Built Python automation"],
        certificates=[],
        skills=["Python", "REST APIs", "SQL"],
        interested_roles=["Python Developer"],
        avoid_roles=["Unpaid Internship"],
        preferred_locations=["Berlin", "Remote"],
        work_authorization="Authorized to work in Germany",
        salary_expectation="Open",
        resume_path="data/resume.pdf",
        cover_letter_style="Professional",
    )


def job() -> JobPosting:
    return JobPosting(
        id="1",
        title="Python Developer",
        company="Example",
        location="Berlin",
        url="https://example.com",
        description="Build backend services with Python and REST APIs.",
        requirements=["Python", "REST APIs", "SQL"],
    )


def llm_result(**overrides) -> dict:
    base = {
        "decision": "apply",
        "score": 90,
        "confidence": 0.9,
        "direct_matches": ["Python"],
        "transferable_matches": [],
        "missing_skills": [],
        "hard_requirement_failures": [],
        "experience_fit": "good",
        "interest_fit": "good",
        "reason": "Good match.",
    }
    base.update(overrides)
    return base


class EvaluateJobHardVetoTest(unittest.TestCase):
    @patch("job_bot.evaluate.evaluate_with_ollama")
    def test_llm_hard_requirement_failure_forces_no_apply(self, mock_evaluate) -> None:
        mock_evaluate.return_value = llm_result(
            hard_requirement_failures=["Requires EU work authorization"]
        )

        result = evaluate_job(profile=profile(), job=job(), min_score=0)

        self.assertEqual(result["decision"], "no apply")
        self.assertIn(
            "LLM: Requires EU work authorization",
            result["decision_basis"]["hard_vetoes"],
        )

    @patch("job_bot.evaluate.evaluate_with_ollama")
    def test_apply_when_llm_agrees_and_no_hard_failures(self, mock_evaluate) -> None:
        mock_evaluate.return_value = llm_result()

        result = evaluate_job(profile=profile(), job=job(), min_score=0)

        self.assertEqual(result["decision"], "apply")


if __name__ == "__main__":
    unittest.main()
