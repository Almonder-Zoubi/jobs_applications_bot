import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class EvaluateScriptTest(unittest.TestCase):
    def test_evaluate_script_is_read_only_and_returns_decision(self) -> None:
        fixture_url = (ROOT / "tests" / "fixtures" / "ml_engineer_job.html").as_uri()

        completed = subprocess.run(
            [sys.executable, "test_url.py", "--url", fixture_url, "--no-llm"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        result = json.loads(completed.stdout)
        self.assertEqual(result["mode"], "evaluate_only")
        self.assertFalse(result["will_apply"])
        self.assertEqual(result["decision"], "apply")
        self.assertTrue(result["suitable"])
        self.assertGreaterEqual(result["score"], result["threshold"])
        self.assertIn("decision_basis", result)
        self.assertIn("role_description_full", result)
        self.assertIn("output_path", result)
        self.assertIn("profile_context_source", result["decision_basis"])
        self.assertFalse(result["decision_basis"]["profile_context_used_by_llm"])


if __name__ == "__main__":
    unittest.main()
