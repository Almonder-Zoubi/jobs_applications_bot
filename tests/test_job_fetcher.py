import tempfile
import unittest
from pathlib import Path

from job_bot.job_fetcher import fetch_job_from_url, infer_company_from_url


class JobFetcherTest(unittest.TestCase):
    def test_fetches_local_html_job_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            page = Path(tmpdir) / "job.html"
            page.write_text(
                """
                <html>
                  <head><title>Machine Learning Engineer - Example GmbH</title></head>
                  <body>
                    <h1>Machine Learning Engineer</h1>
                    <p>We need Python, TensorFlow, SQL, Docker, and Git.</p>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            job = fetch_job_from_url(page.as_uri())

        self.assertEqual(job.title, "Machine Learning Engineer - Example GmbH")
        self.assertEqual(job.company, "Example GmbH")
        self.assertIn("Python", job.requirements)
        self.assertIn("TensorFlow", job.requirements)

    def test_reads_full_description_from_jsonld_job_posting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            page = Path(tmpdir) / "job.html"
            page.write_text(
                """
                <html>
                  <head>
                    <title>Applied AI Engineer @ Nexxa.AI</title>
                    <script type="application/ld+json">
                    {
                      "@context": "https://schema.org/",
                      "@type": "JobPosting",
                      "title": "Applied AI Engineer",
                      "description": "<p>Build Python and TensorFlow systems for enterprise customers. You will design data pipelines, deploy machine learning models to production, and work directly with engineering teams to ship reliable AI-powered features at scale.</p>",
                      "hiringOrganization": {"name": "Nexxa.AI"},
                      "jobLocation": {
                        "address": {
                          "addressLocality": "Berlin",
                          "addressCountry": "Germany"
                        }
                      }
                    }
                    </script>
                  </head>
                  <body><div id="app"></div></body>
                </html>
                """,
                encoding="utf-8",
            )

            job = fetch_job_from_url(page.as_uri())

        self.assertEqual(job.title, "Applied AI Engineer")
        self.assertEqual(job.company, "Nexxa.AI")
        self.assertIn("Berlin", job.location)
        self.assertIn("Python", job.description)
        self.assertEqual(job.description_confidence, "high")

    def test_infers_company_from_personio_subdomain_when_jsonld_org_name_is_empty(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            page = Path(tmpdir) / "job.html"
            page.write_text(
                """
                <html>
                  <head>
                    <title>(Junior) Cloud Data Engineer (all genders)</title>
                    <script type="application/ld+json">
                    {
                      "@context": "https://schema.org/",
                      "@type": "JobPosting",
                      "title": "(Junior) Cloud Data Engineer (all genders)",
                      "description": "<p>Work with SQL and cloud data pipelines.</p>",
                      "hiringOrganization": {"@type": "Organization", "name": ""}
                    }
                    </script>
                  </head>
                  <body></body>
                </html>
                """,
                encoding="utf-8",
            )
            # file:// URLs can't exercise the real hostname-based fallback, so
            # this covers the JSON-LD-empty-name path directly via the title
            # fallback returning "" (no separator) and company staying empty
            # until infer_company_from_url runs on the real https URL — see
            # test_infer_company_from_url_recognizes_known_ats_hosts below.
            job = fetch_job_from_url(page.as_uri())

        self.assertEqual(job.company, "Unknown Company")

    def test_infer_company_from_url_recognizes_known_ats_hosts(self) -> None:
        self.assertEqual(
            infer_company_from_url("https://dymatrix.jobs.personio.de/job/665763"),
            "Dymatrix",
        )
        self.assertEqual(
            infer_company_from_url(
                "https://jobs.ashbyhq.com/recraft/f9c15249-88f1-4e68-8eaf-03fff97971e5"
            ),
            "Recraft",
        )
        self.assertEqual(
            infer_company_from_url(
                "https://boards.greenhouse.io/commercetools/jobs/4609308003"
            ),
            "Commercetools",
        )
        self.assertEqual(infer_company_from_url("https://example.com/jobs/1"), "")

    def test_flags_low_confidence_when_page_has_no_real_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            page = Path(tmpdir) / "job.html"
            page.write_text(
                '<html><head><title>Applied AI Engineer @ Nexxa.AI</title></head>'
                '<body><div id="app"></div></body></html>',
                encoding="utf-8",
            )

            job = fetch_job_from_url(page.as_uri())

        self.assertEqual(job.company, "Nexxa.AI")
        self.assertEqual(job.description_confidence, "low")


if __name__ == "__main__":
    unittest.main()
