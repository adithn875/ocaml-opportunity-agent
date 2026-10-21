import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ocaml_agent.ocaml_ranking import OCAML_RANKING, calculate_final_score


class OcamlFinalRankingTests(unittest.TestCase):
    @patch("ocaml_agent.ocaml_ranking.subprocess.run")
    def test_sends_validated_scores_and_returns_the_raw_result(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe", "--calculate-final-score"],
            returncode=0,
            stdout='{"final_score":1.2999999999999998}\n',
            stderr="",
        )

        result = calculate_final_score(technical_score=1, practicality_score=2)

        self.assertEqual(result, 1.2999999999999998)
        self.assertEqual(
            mock_run.call_args.args[0][-1], "--calculate-final-score"
        )
        self.assertEqual(
            json.loads(mock_run.call_args.kwargs["input"]),
            {"technical_score": 1.0, "practicality_score": 2.0},
        )

    @patch("ocaml_agent.ocaml_ranking.subprocess.run")
    def test_rejects_invalid_input_before_starting_the_evaluator(self, mock_run):
        for technical, practicality in (
            (None, 70),
            ("70", 70),
            (True, 70),
            (float("nan"), 70),
            (-0.1, 70),
            (70, 100.1),
        ):
            with self.subTest(technical=technical, practicality=practicality):
                with self.assertRaises(ValueError):
                    calculate_final_score(
                        technical_score=technical,
                        practicality_score=practicality,
                    )

        mock_run.assert_not_called()

    @patch("ocaml_agent.ocaml_ranking.subprocess.run")
    def test_rejects_invalid_evaluator_output(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["main.exe", "--calculate-final-score"],
            returncode=0,
            stdout='{"final_score":"87.5"}\n',
            stderr="",
        )

        with self.assertRaisesRegex(RuntimeError, "invalid 'final_score'"):
            calculate_final_score(technical_score=95, practicality_score=70)

    @patch("ocaml_agent.ocaml_ranking.subprocess.run")
    def test_reports_missing_executable(self, mock_run):
        mock_run.side_effect = FileNotFoundError("main.exe not found")

        with self.assertRaisesRegex(RuntimeError, "main.exe not found"):
            calculate_final_score(technical_score=95, practicality_score=70)

    @unittest.skipUnless(OCAML_RANKING.is_file(), "run dune build first")
    def test_matches_the_pre_migration_formula_across_representative_inputs(self):
        cases = (
            (0, 0),
            (100, 100),
            (95, 70),
            (0, 100),
            (100, 0),
            (1, 2),
            (33.333333333333336, 66.66666666666667),
        )

        for technical, practicality in cases:
            with self.subTest(technical=technical, practicality=practicality):
                expected = (0.70 * technical) + (0.30 * practicality)
                self.assertEqual(
                    calculate_final_score(
                        technical_score=technical,
                        practicality_score=practicality,
                    ),
                    expected,
                )

    @unittest.skipUnless(OCAML_RANKING.is_file(), "run dune build first")
    def test_cli_rejects_missing_or_malformed_score_fields(self):
        for payload, expected_message in (
            ("{}\n", "missing technical_score"),
            ('{"technical_score":95,"practicality_score":null}\n', "practicality_score"),
            ("{not JSON}\n", "invalid JSON"),
        ):
            with self.subTest(payload=payload):
                result = subprocess.run(
                    [str(OCAML_RANKING), "--calculate-final-score"],
                    input=payload,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 2)
                self.assertIn(expected_message, result.stderr)
                self.assertEqual(result.stdout, "")

    @unittest.skipUnless(OCAML_RANKING.is_file(), "run dune build first")
    def test_evaluator_path_is_independent_of_current_directory(self):
        original_directory = os.getcwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                result = calculate_final_score(
                    technical_score=95, practicality_score=70
                )
            finally:
                os.chdir(original_directory)

        self.assertEqual(result, 87.5)
