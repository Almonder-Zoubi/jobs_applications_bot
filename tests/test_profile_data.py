import unittest

from job_bot.profile_data import profile_from_structured_data


class ProfileDataTest(unittest.TestCase):
    def test_flattens_structured_profile(self) -> None:
        profile = profile_from_structured_data(
            {
                "name": "Almonder",
                "surname": "Zoubi",
                "email": "almonder@example.com",
                "phone_number": "+49 123",
                "address": "Brandenburg, Germany",
                "skills": [
                    {
                        "Programming Languages": ["Python", "Java"],
                        "Tools": ["Docker", "Git"],
                    }
                ],
                "experience": [
                    {
                        "company": "Example",
                        "position": "AI Engineer",
                        "responsibilities": ["Built a RAG system"],
                        "achievements": ["Improved search quality"],
                    }
                ],
                "interested_roles": ["AI Engineer"],
            }
        )

        self.assertEqual(profile.name, "Almonder Zoubi")
        self.assertIn("Python", profile.skills)
        self.assertIn("Built a RAG system", profile.background)
        self.assertIn("AI Engineer", profile.interested_roles)

    def test_flattens_nested_locations_salary_and_education(self) -> None:
        profile = profile_from_structured_data(
            {
                "name": "Almonder",
                "surname": "Zoubi",
                "profile_summary": "Written CV summary.",
                "preferred_locations": {"Germany": ["Berlin", "Munich"]},
                "salary_expectations": {"currency": "EUR", "amount": 40000},
                "education": [
                    {
                        "degree": "B.Sc. Informatik",
                        "major": "Intelligent Systems",
                        "institution": "THB",
                        "relevant_courses": ["Machine Learning"],
                    }
                ],
                "projects": {"academic": ["Built a FAISS-based search system."]},
            }
        )

        self.assertEqual(profile.cv_summary, "Written CV summary.")
        self.assertIn("Germany", profile.preferred_locations)
        self.assertIn("Berlin", profile.preferred_locations)
        self.assertEqual(profile.salary_expectation, "40,000 EUR")
        self.assertTrue(
            any("Intelligent Systems" in item for item in profile.background)
        )
        self.assertIn("Machine Learning", profile.background)
        self.assertIn("Built a FAISS-based search system.", profile.background)


if __name__ == "__main__":
    unittest.main()
