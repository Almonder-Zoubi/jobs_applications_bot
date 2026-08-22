import unittest

from job_bot.letter_templates import select_letter_template
from job_bot.models import JobPosting


TEMPLATES = {
    "ai_ml_llm": {
        "english": "files/Cover_Letter_AI_ML_LLM.docx",
        "german": "files/Anschreiben_AI_ML_LLM.docx",
        "target_roles": ["AI Engineer", "Machine Learning Engineer", "LLM Engineer"],
    },
    "software_engineering": {
        "english": "files/Cover_Letter_Software_Engineering.docx",
        "german": "files/Anschreiben_Software_Engineering.docx",
        "target_roles": ["Software Engineer", "Backend Developer", "Python Developer"],
    },
}


def job(title: str, requirements: list[str] | None = None) -> JobPosting:
    return JobPosting(
        id="1",
        title=title,
        company="Example",
        location="Berlin",
        url="https://example.com",
        description="",
        requirements=requirements or [],
    )


class SelectLetterTemplateTest(unittest.TestCase):
    def test_picks_best_matching_category_by_title(self) -> None:
        template = select_letter_template(job("Machine Learning Engineer"), TEMPLATES)

        self.assertIsNotNone(template)
        self.assertEqual(template["category"], "ai_ml_llm")
        self.assertEqual(template["english"], "files/Cover_Letter_AI_ML_LLM.docx")

    def test_picks_different_category_for_backend_role(self) -> None:
        template = select_letter_template(job("Backend Developer"), TEMPLATES)

        self.assertEqual(template["category"], "software_engineering")

    def test_returns_none_when_no_category_matches(self) -> None:
        template = select_letter_template(job("Sales Manager"), TEMPLATES)

        self.assertIsNone(template)

    def test_returns_none_for_empty_templates(self) -> None:
        template = select_letter_template(job("AI Engineer"), {})

        self.assertIsNone(template)


if __name__ == "__main__":
    unittest.main()
