
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ocaml_agent.ocaml_candidates import OCAML_EVALUATOR, evaluate_candidate


class EvaluateCandidateTests(unittest.TestCase):
    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_returns_valid_candidate_decision(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe", "--evaluate-candidate"],
            returncode=0,
            stdout=json.dumps(
                {
                    "accepted": True,
                    "reason": "explicit OCaml-relevant title signal: OCaml, Compiler",
                    "title_signals": ["OCaml", "Compiler"],
                }
            ),
            stderr="",
        )

        result = evaluate_candidate(
            {
                "title": "OCaml Compiler Engineer",
                "score": 25,
                "description": "Build compiler tooling.",
                "source": None,
            }
        )

        self.assertTrue(result["accepted"])
        self.assertEqual(result["title_signals"], ["OCaml", "Compiler"])
        self.assertEqual(
            mock_run.call_args.args[0][-1],
            "--evaluate-candidate",
        )
        sent_payload = json.loads(mock_run.call_args.kwargs["input"])
        self.assertEqual(sent_payload["title"], "OCaml Compiler Engineer")

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_missing_score_is_sent_as_zero(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe"],
            returncode=0,
            stdout=json.dumps(
                {"accepted": False, "reason": "no evidence", "title_signals": []}
            ),
            stderr="",
        )

        evaluate_candidate({"title": "Engineer"})

        sent_payload = json.loads(mock_run.call_args.kwargs["input"])
        self.assertEqual(sent_payload["score"], 0.0)

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_rejects_malformed_input_before_starting_the_evaluator(self, mock_run):
        invalid_jobs = (
            {"title": "Engineer", "score": "30"},
            {"title": "Engineer", "score": float("nan")},
            {"title": "Engineer", "score": 10**1000},
            {"title": "Engineer", "score": True},
            {"title": ["Engineer"]},
            {"title": "Engineer", "description": 42},
            {"title": "Engineer", "source": 42},
        )

        for job in invalid_jobs:
            with self.subTest(job=job):
                with self.assertRaises(ValueError):
                    evaluate_candidate(job)

        mock_run.assert_not_called()

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_rejects_invalid_json(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe"],
            returncode=0,
            stdout="not JSON",
            stderr="",
        )

        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            evaluate_candidate({"title": "Engineer"})

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_rejects_invalid_decision_shape(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe"],
            returncode=0,
            stdout=json.dumps({"accepted": "yes"}),
            stderr="",
        )

        with self.assertRaisesRegex(RuntimeError, "invalid 'accepted'"):
            evaluate_candidate({"title": "Engineer"})

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_reports_subprocess_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["main.exe"], stderr="OCaml process failed"
        )

        with self.assertRaisesRegex(RuntimeError, "evaluator failed"):
            evaluate_candidate({"title": "Engineer"})

    @patch("ocaml_agent.ocaml_candidates.subprocess.run")
    def test_reports_missing_executable(self, mock_run):
        mock_run.side_effect = FileNotFoundError("main.exe not found")

        with self.assertRaisesRegex(RuntimeError, "main.exe not found"):
            evaluate_candidate({"title": "Engineer"})

    @unittest.skipUnless(OCAML_EVALUATOR.is_file(), "run dune build first")
    def test_evaluator_path_is_independent_of_current_directory(self):
        original_directory = os.getcwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                decision = evaluate_candidate(
                    {"title": "OCaml Compiler Engineer", "score": 0}
                )
            finally:
                os.chdir(original_directory)

        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["title_signals"], ["OCaml", "Compiler"])

    @unittest.skipUnless(OCAML_EVALUATOR.is_file(), "run dune build first")
    def test_cli_rejects_invalid_json_and_wrong_field_types(self):
        for payload, expected_message in (
            ("{not JSON}\n", "invalid JSON"),
            ('{"title":"Engineer","score":"30"}\n', "candidate score"),
        ):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [str(OCAML_EVALUATOR), "--evaluate-candidate"],
                    input=payload,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn(expected_message, result.stderr)
                self.assertEqual(result.stdout, "")

    @unittest.skipUnless(OCAML_EVALUATOR.is_file(), "run dune build first")
    def test_existing_json_scoring_mode_is_unchanged(self):
        result = subprocess.run(
            [str(OCAML_EVALUATOR), "--json"],
            input="OCaml Compiler Engineer\n\n\nWork on the OCaml compiler.\n",
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(
            json.loads(result.stdout),
            {
                "title": "OCaml Compiler Engineer",
                "score": 55,
                "signals": [
                    {"name": "Compiler", "weight": 25},
                    {"name": "OCaml", "weight": 30},
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
