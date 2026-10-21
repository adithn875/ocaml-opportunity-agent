import json
import subprocess
import unittest
from unittest.mock import patch

from ocaml_agent.score_jobs import score_job


class ScoreJobsTests(unittest.TestCase):
    @patch("ocaml_agent.score_jobs.subprocess.run")
    def test_score_job_reads_score_from_json(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ocaml-scorer", "--json"],
            returncode=0,
            stdout=json.dumps(
                {
                    "title": "OCaml Compiler Engineer",
                    "score": 70,
                    "signals": [
                        {"name": "OCaml", "weight": 30},
                        {"name": "Compiler", "weight": 25},
                        {"name": "Functional programming", "weight": 15},
                    ],
                }
            ),
            stderr="",
        )

        job = {
            "title": "OCaml Compiler Engineer",
            "company": "Example Company",
            "location": "Remote",
            "description": "Work on OCaml compiler tools.",
        }

        score = score_job(job)

        self.assertEqual(score, 70)
        self.assertIn("--json", mock_run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
