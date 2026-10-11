import unittest

from ocaml_agent.ranking import calculate_final_score


class FinalRankingTests(unittest.TestCase):
    def test_uses_seventy_percent_technical_and_thirty_percent_practicality(self):
        self.assertAlmostEqual(
            calculate_final_score(technical_score=95, practicality_score=70),
            87.5,
        )

    def test_equal_inputs_produce_the_same_final_score(self):
        self.assertAlmostEqual(
            calculate_final_score(technical_score=85, practicality_score=85),
            85.0,
        )

    def test_zero_scores_produce_zero(self):
        self.assertAlmostEqual(
            calculate_final_score(technical_score=0, practicality_score=0),
            0.0,
        )

    def test_maximum_scores_produce_one_hundred(self):
        self.assertAlmostEqual(
            calculate_final_score(technical_score=100, practicality_score=100),
            100.0,
        )

    def test_rejects_scores_outside_zero_to_one_hundred(self):
        for score in (-1, 101):
            with self.subTest(score=score):
                with self.assertRaises(ValueError):
                    calculate_final_score(
                        technical_score=score,
                        practicality_score=70,
                    )

    def test_rejects_invalid_practicality_score(self):
        with self.assertRaises(ValueError):
            calculate_final_score(
                technical_score=80,
                practicality_score=101,
            )


if __name__ == "__main__":
    unittest.main()
