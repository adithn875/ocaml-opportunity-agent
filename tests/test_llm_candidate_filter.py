import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ocaml_agent import llm_score


class LlmCandidateFilterTests(unittest.TestCase):
    def test_rejected_candidates_do_not_reach_the_llm(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "agent.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE seen_items (
                        id INTEGER PRIMARY KEY,
                        title TEXT,
                        company TEXT,
                        location TEXT,
                        description TEXT,
                        score REAL,
                        source TEXT,
                        llm_score INTEGER,
                        llm_reason TEXT,
                        llm_model TEXT,
                        practicality_score INTEGER,
                        opportunity_class TEXT,
                        practicality_reason TEXT
                    )
                    """
                )
                connection.executemany(
                    """
                    INSERT INTO seen_items
                        (id, title, company, location, description, score, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (1, "[ANN] OCaml release", None, None, "Announcement", 100, None),
                        (2, "OCaml Engineer", None, None, "Build compilers", 0, None),
                    ],
                )
                connection.commit()
            finally:
                connection.close()

            with (
                patch.object(llm_score, "DB_PATH", database_path),
                patch.object(
                    llm_score,
                    "score_job",
                    return_value=(90, 80, "Target", "OCaml", "Suitable"),
                ) as score_job,
                patch.object(sys, "argv", ["llm_score.py"]),
                redirect_stdout(io.StringIO()),
            ):
                llm_score.main()

        self.assertEqual(score_job.call_count, 1)
        self.assertEqual(score_job.call_args.args[0]["id"], 2)
