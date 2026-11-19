import sqlite3
import tempfile
import unittest
from pathlib import Path

from ocaml_agent import db


class DatabaseMigrationTests(unittest.TestCase):
    def test_connect_creates_the_latest_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"

            with db.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(seen_items)")
                }
                versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ]
                source_runs_exists = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'source_runs'
                    """
                ).fetchone()

        self.assertTrue(set(db.SCORING_COLUMNS).issubset(columns))
        self.assertEqual(versions, [1, 2, 3])
        self.assertIsNotNone(source_runs_exists)

    def test_connect_upgrades_a_legacy_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"

            with sqlite3.connect(database_path) as connection:
                connection.executescript(db.INITIAL_SCHEMA)

            with db.connect(database_path) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(seen_items)")
                }

        self.assertTrue(set(db.SCORING_COLUMNS).issubset(columns))
