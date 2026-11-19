import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ocaml_agent import collect, db


class CollectorRunTests(unittest.TestCase):
    def test_successful_collector_records_source_health(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"

            def collect_one_job():
                with db.connect(database_path) as connection:
                    connection.execute(
                        """
                        INSERT INTO seen_items (canonical_url, title)
                        VALUES (?, ?)
                        """,
                        ("https://example.com/jobs/1", "OCaml Engineer"),
                    )

            with patch.object(collect, "DB_PATH", database_path):
                self.assertTrue(collect.run_collector("Example", collect_one_job))

            with db.connect(database_path) as connection:
                row = connection.execute(
                    """
                    SELECT source, status, new_items, error
                    FROM source_runs
                    """
                ).fetchone()

        self.assertEqual(row, ("Example", "ok", 1, None))

    def test_failed_collector_records_error(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"

            def fail_collection():
                raise RuntimeError("source unavailable")

            with patch.object(collect, "DB_PATH", database_path):
                self.assertFalse(collect.run_collector("Example", fail_collection))

            with db.connect(database_path) as connection:
                row = connection.execute(
                    """
                    SELECT source, status, new_items, error
                    FROM source_runs
                    """
                ).fetchone()

        self.assertEqual(row, ("Example", "failed", 0, "source unavailable"))
