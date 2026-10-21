import io
import sqlite3
import unittest
from contextlib import redirect_stdout

from ocaml_agent.ranking import calculate_final_score, rank_unscored


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

    def test_returns_the_raw_float_without_rounding(self):
        self.assertEqual(
            calculate_final_score(technical_score=1, practicality_score=2),
            1.2999999999999998,
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

    def test_rank_unscored_excludes_missing_and_invalid_scores_and_orders_by_id(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                llm_score REAL,
                practicality_score REAL,
                final_score REAL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO seen_items (id, llm_score, practicality_score, final_score)
            VALUES (?, ?, ?, ?)
            """,
            [
                (7, 80, 70, None),
                (3, 80.0, 70.0, None),
                (4, None, 70, None),
                (5, 101, 70, None),
                (6, 80, -1, None),
                (8, 80, 70, 77.0),
            ],
        )

        output = io.StringIO()
        with redirect_stdout(output):
            count = rank_unscored(connection)

        self.assertEqual(count, 2)
        self.assertEqual(
            output.getvalue(),
            "3: 77.0\n7: 77.0\nWould rank 2 opportunities.\n",
        )
        self.assertEqual(
            connection.execute(
                "SELECT final_score FROM seen_items WHERE id = 3"
            ).fetchone()[0],
            None,
        )
        connection.close()

    def test_rank_unscored_persists_the_unrounded_score_when_writing(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                llm_score REAL,
                practicality_score REAL,
                final_score REAL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO seen_items (id, llm_score, practicality_score, final_score)
            VALUES (1, 1, 2, NULL)
            """
        )

        with redirect_stdout(io.StringIO()):
            count = rank_unscored(connection, dry_run=False)

        self.assertEqual(count, 1)
        self.assertEqual(
            connection.execute(
                "SELECT final_score FROM seen_items WHERE id = 1"
            ).fetchone()[0],
            1.2999999999999998,
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
