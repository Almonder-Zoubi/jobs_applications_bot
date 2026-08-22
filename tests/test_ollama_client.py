import unittest

from job_bot.models import CandidateProfile, JobPosting, MatchResult
from job_bot.ollama_client import (
    build_evaluation_prompt,
    compute_batch_num_ctx,
    estimate_num_ctx,
    fallback_evaluation,
    normalize_llm_result,
)


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


class ComputeBatchNumCtxTest(unittest.TestCase):
    def test_returns_smallest_bucket_for_empty_batch(self) -> None:
        self.assertEqual(compute_batch_num_ctx(profile(), []), 4096)

    def test_sizes_to_the_largest_job_in_the_batch(self) -> None:
        small_job = job()
        large_job = JobPosting(
            id="2",
            title="Python Developer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="x" * 40000,
            requirements=["Python"],
        )

        shared_ctx = compute_batch_num_ctx(profile(), [small_job, large_job])

        self.assertEqual(shared_ctx, estimate_num_ctx(
            build_evaluation_prompt(profile(), large_job, match(), 60, "")
        ))


class NormalizeLlmResultTest(unittest.TestCase):
    def test_normalizes_uppercase_decision_and_clamps_ranges(self) -> None:
        result = normalize_llm_result(
            {
                "decision": "APPLY",
                "score": 150,
                "confidence": 1.5,
                "direct_matches": ["Python"],
                "transferable_matches": [
                    {"required": "FastAPI", "candidate_has": "Django", "gap": "small"}
                ],
                "missing_skills": [{"skill": "Docker", "importance": "medium"}],
                "hard_requirement_failures": [],
                "experience_fit": "good",
                "interest_fit": "excellent",
                "reason": "Strong match.",
            }
        )

        self.assertEqual(result["decision"], "apply")
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["transferable_matches"][0]["gap"], "small")
        self.assertEqual(result["missing_skills"][0]["importance"], "medium")

    def test_unknown_decision_value_falls_back_to_no_apply(self) -> None:
        result = normalize_llm_result({"decision": "maybe"})

        self.assertEqual(result["decision"], "no apply")

    def test_drops_malformed_transferable_match_entries(self) -> None:
        result = normalize_llm_result(
            {"transferable_matches": [{"required": "FastAPI"}, "not a dict"]}
        )

        self.assertEqual(result["transferable_matches"], [])


class FallbackEvaluationTest(unittest.TestCase):
    def test_includes_new_schema_fields(self) -> None:
        result = fallback_evaluation(match(), threshold=60)

        self.assertEqual(result["decision"], "apply")
        self.assertIn("direct_matches", result)
        self.assertEqual(
            result["missing_skills"], []
        )  # match() fixture has no missing_terms
        self.assertEqual(result["hard_requirement_failures"], [])


if __name__ == "__main__":
    unittest.main()
