import unittest

from job_bot.models import CandidateProfile, JobPosting, MatchResult
from job_bot.ollama_client import build_evaluation_prompt, estimate_num_ctx


def profile() -> CandidateProfile:
    return CandidateProfile(
        name="Test User",
        email="test@example.com",
        phone="+49 000",
        location="Berlin",
        cv_summary="Python automation engineer",
        background=["Built Python automation"],
        certificates=[],
        skills=["Python"],
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
        description="Build automation with Python.",
        requirements=["Python"],
    )


def match() -> MatchResult:
    return MatchResult(score=80, matched_terms=["Python"], missing_terms=[], reasons=[])


class BuildEvaluationPromptTest(unittest.TestCase):
    def test_includes_profile_context_when_provided(self) -> None:
        prompt = build_evaluation_prompt(
            profile(), job(), match(), threshold=60, profile_context="Favor Python roles."
        )

        self.assertIn("Candidate's own context and evaluation guidance", prompt)
        self.assertIn("Favor Python roles.", prompt)

    def test_omits_context_section_when_empty(self) -> None:
        prompt = build_evaluation_prompt(profile(), job(), match(), threshold=60)

        self.assertNotIn("Candidate's own context and evaluation guidance", prompt)

    def test_includes_description_confidence_in_job_snapshot(self) -> None:
        low_confidence_job = JobPosting(
            id="2",
            title="Applied AI Engineer",
            company="Nexxa.AI",
            location="Germany",
            url="https://example.com",
            description="Applied AI Engineer",
            requirements=[],
            description_confidence="low",
        )

        prompt = build_evaluation_prompt(profile(), low_confidence_job, match(), threshold=60)

        self.assertIn('"description_confidence": "low"', prompt)


class EstimateNumCtxTest(unittest.TestCase):
    def test_grows_with_prompt_length(self) -> None:
        short_estimate = estimate_num_ctx("short text")
        long_estimate = estimate_num_ctx("x" * 40000)

        self.assertGreater(long_estimate, short_estimate)
        self.assertGreaterEqual(long_estimate, 16384)

    def test_never_below_smallest_bucket(self) -> None:
        self.assertEqual(estimate_num_ctx(""), 4096)


if __name__ == "__main__":
    unittest.main()
