import unittest
from dataclasses import replace

from job_bot.matcher import detect_seniority_signals, score_job
from job_bot.models import CandidateProfile, JobPosting


def profile() -> CandidateProfile:
    return CandidateProfile(
        name="Test User",
        email="test@example.com",
        phone="+49 000",
        location="Berlin",
        cv_summary="Python automation engineer",
        background=["Built Python automation", "Created REST APIs"],
        certificates=["AWS Certified Cloud Practitioner"],
        skills=[
            "Python",
            "REST APIs",
            "MySQL",
            "PostgreSQL",
            "Automation",
            "Natural Language Processing",
        ],
        interested_roles=["Python Developer", "Automation Engineer"],
        avoid_roles=["Unpaid Internship"],
        preferred_locations=["Berlin", "Remote"],
        work_authorization="Authorized to work in Germany",
        salary_expectation="Open",
        resume_path="data/resume.pdf",
        cover_letter_style="Professional",
    )


class MatcherTest(unittest.TestCase):
    def test_scores_matching_job_high_enough(self) -> None:
        job = JobPosting(
            id="1",
            title="Python Developer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="Build automation with Python and REST APIs.",
            requirements=["Python", "REST APIs", "SQL"],
        )

        result = score_job(profile(), job)

        self.assertGreaterEqual(result.score, 60)
        self.assertIn("Python", result.matched_terms)

    def test_avoid_role_scores_zero(self) -> None:
        job = JobPosting(
            id="2",
            title="Unpaid Internship",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="Internship role.",
            requirements=["Python"],
        )

        result = score_job(profile(), job)

        self.assertEqual(result.score, 0)

    def test_avoid_role_does_not_match_page_footer_noise(self) -> None:
        job = JobPosting(
            id="footer-sales",
            title="Python Developer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="Build Python services. Footer links: Sales, Marketing, Support.",
            requirements=["Python", "REST APIs"],
        )

        result = score_job(profile(), job)

        self.assertGreater(result.score, 0)

    def test_aliases_cover_common_job_requirement_terms(self) -> None:
        job = JobPosting(
            id="3",
            title="Machine Learning Engineer",
            company="Example",
            location="Remote Germany",
            url="https://example.com",
            description="Build NLP systems with Python and SQL-backed services.",
            requirements=["Python", "NLP", "SQL"],
        )

        result = score_job(profile(), job)

        self.assertIn("Python", result.matched_terms)
        self.assertNotIn("NLP", result.missing_terms)
        self.assertNotIn("SQL", result.missing_terms)

    def test_penalizes_senior_experience_requirement_in_description_body(self) -> None:
        job = JobPosting(
            id="4",
            title="Applied AI Engineer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description=(
                "Build Python and ML systems. Requires 5-10+ years in "
                "engineering roles. We're looking for a senior engineer."
            ),
            requirements=["Python"],
        )

        with_signals = score_job(profile(), job)

        clean_job = JobPosting(
            id="5",
            title="Applied AI Engineer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="Build Python and ML systems for a growing team.",
            requirements=["Python"],
        )
        without_signals = score_job(profile(), clean_job)

        self.assertLess(with_signals.score, without_signals.score)
        self.assertTrue(
            any("Seniority" in reason for reason in with_signals.reasons)
        )


class ShortAliasFalsePositiveTest(unittest.TestCase):
    def rag_profile(self) -> CandidateProfile:
        base = profile()
        return replace(base, skills=base.skills + ["Retreival-Augmented Generation (RAG)"])

    def test_rag_alias_does_not_match_inside_paragraph(self) -> None:
        job = JobPosting(
            id="6",
            title="Full-Stack Software Engineer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="Please read the first paragraph before you apply.",
            requirements=[],
        )

        result = score_job(self.rag_profile(), job)

        self.assertNotIn("Retreival-Augmented Generation (RAG)", result.matched_terms)

    def test_rag_alias_still_matches_real_mention(self) -> None:
        job = JobPosting(
            id="7",
            title="AI Engineer",
            company="Example",
            location="Berlin",
            url="https://example.com",
            description="We build RAG pipelines for search.",
            requirements=[],
        )

        result = score_job(self.rag_profile(), job)

        self.assertIn("Retreival-Augmented Generation (RAG)", result.matched_terms)


class DetectSeniorSignalsTest(unittest.TestCase):
    def test_detects_years_and_seniority_titles(self) -> None:
        signals = detect_seniority_signals(
            "5–10+ years in engineering roles. A senior engineer role."
        )

        self.assertTrue(any("5" in signal for signal in signals))
        self.assertIn('mentions "senior"', signals)

    def test_low_year_counts_are_not_flagged(self) -> None:
        signals = detect_seniority_signals(
            "You'll be mentored by senior engineers on the team. 0-1 years is fine."
        )

        # "senior" is still surfaced as a soft signal (deferred to the LLM/human
        # to judge context); only the years-of-experience check has a threshold.
        self.assertIn('mentions "senior"', signals)
        self.assertFalse(any("0-1" in signal for signal in signals))

    def test_no_signals_for_plain_description(self) -> None:
        signals = detect_seniority_signals("Build Python services with our team.")

        self.assertEqual(signals, [])


if __name__ == "__main__":
    unittest.main()
