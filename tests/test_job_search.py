import unittest

from job_bot.job_search import job_posting_from_arbeitnow


class JobPostingFromArbeitnowTest(unittest.TestCase):
    def test_converts_listing_fields_and_strips_html_description(self) -> None:
        listing = {
            "title": "Python Developer",
            "company_name": "Example GmbH",
            "location": "Berlin",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/example/python-dev-1",
            "description": "<p>Build <strong>Python</strong> and Docker services.</p>",
            "tags": ["Python", "Docker", "Python"],
        }

        job = job_posting_from_arbeitnow(listing)

        self.assertEqual(job.title, "Python Developer")
        self.assertEqual(job.company, "Example GmbH")
        self.assertIn("Remote", job.location)
        self.assertIn("Python", job.description)
        self.assertNotIn("<p>", job.description)
        self.assertIn("Python", job.requirements)
        self.assertIn("Docker", job.requirements)
        # tags are deduped against each other and against inferred requirements
        self.assertEqual(job.requirements.count("Python"), 1)

    def test_does_not_duplicate_remote_when_already_in_location(self) -> None:
        listing = {
            "title": "Data Engineer",
            "company_name": "Example GmbH",
            "location": "Berlin, remote",
            "remote": True,
            "url": "https://www.arbeitnow.com/jobs/companies/example/data-eng-1",
            "description": "Build data pipelines.",
            "tags": [],
        }

        job = job_posting_from_arbeitnow(listing)

        self.assertEqual(job.location.casefold().count("remote"), 1)

    def test_flags_low_confidence_for_thin_descriptions(self) -> None:
        listing = {
            "title": "Data Engineer",
            "company_name": "Example GmbH",
            "location": "Berlin",
            "remote": False,
            "url": "https://www.arbeitnow.com/jobs/companies/example/data-eng-2",
            "description": "Short.",
            "tags": [],
        }

        job = job_posting_from_arbeitnow(listing)

        self.assertEqual(job.description_confidence, "low")


if __name__ == "__main__":
    unittest.main()
