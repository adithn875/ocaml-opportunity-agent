import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from ocaml_agent import notify
from ocaml_agent.notify import build_message


class NotificationTests(unittest.TestCase):
    def _create_notification_database(self, path, rows):
        connection = sqlite3.connect(path)
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                score REAL,
                llm_score REAL,
                final_score REAL,
                description TEXT,
                canonical_url TEXT,
                source TEXT,
                emailed INTEGER,
                posted_date TEXT,
                deadline TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO seen_items
                (id, title, company, location, score, llm_score, final_score,
                 description, canonical_url, source, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
        connection.close()

    def test_clean_description_normalizes_html_to_plain_text(self):
        cases = (
            (
                "<p>First paragraph.</p><p>Second<br>line.</p>",
                "First paragraph. Second line.",
            ),
            (
                "<ul><li>OCaml</li><li>Compiler &amp; tooling</li></ul>",
                "• OCaml • Compiler & tooling",
            ),
            (
                "<p><strong>Typed</strong> <em>functional</em> programming.</p>",
                "Typed functional programming.",
            ),
            ("OCaml&nbsp;&amp;&nbsp;OxCaml", "OCaml & OxCaml"),
            ("  Plain\n\ttext   remains readable.  ", "Plain text remains readable."),
            ("Use <T> for a type parameter.", "Use <T> for a type parameter."),
            (
                "<p>Visible text.</p><script>alert('hidden')</script>"
                "<style>.hidden { display: none; }</style><p>More text.</p>",
                "Visible text. More text.",
            ),
        )

        for description, expected in cases:
            with self.subTest(description=description):
                self.assertEqual(notify.clean_description(description), expected)

        self.assertEqual(notify.clean_description(None), "")
        self.assertEqual(notify.clean_description(""), "")
        self.assertEqual(notify.clean_description(42), "")

    def test_missing_scores_do_not_crash_message_builder(self):
        strong_rows = [
            (
                "OCaml Developer",
                "Example Company",
                "Remote",
                None,
                None,
                None,
                "Work with OCaml.",
                "https://example.com/job",
            )
        ]

        other_rows = [
            ("Functional Programmer", "Example Company", None)
        ]

        message = build_message(strong_rows, other_rows)

        self.assertIn("OCaml Developer", message)
        self.assertIn("Functional Programmer", message)
        self.assertIn("Final: N/A", message)
        self.assertIn("OCaml: N/A", message)
        self.assertIn("AI: N/A", message)

    def test_legacy_jane_street_rows_are_rechecked_before_notification(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                score REAL,
                llm_score REAL,
                practicality_score REAL,
                final_score REAL,
                description TEXT,
                canonical_url TEXT,
                source TEXT,
                emailed INTEGER,
                posted_date TEXT,
                deadline TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO seen_items
                (id, title, company, location, score, llm_score,
                 practicality_score, final_score, description,
                 canonical_url, source, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "Quantitative Trader",
                    "Jane Street",
                    "NYC",
                    60,
                    95,
                    85,
                    92,
                    "Trade markets. Jane Street uses OCaml as its primary development language.",
                    "https://example.com/trader",
                    "Jane Street",
                    0,
                ),
                (
                    2,
                    "Compiler Engineer",
                    "Jane Street",
                    "NYC",
                    90,
                    95,
                    75,
                    89,
                    "Implement compiler infrastructure for OxCaml.",
                    "https://example.com/compiler",
                    "Jane Street",
                    0,
                ),
                (
                    3,
                    "OCaml Developer",
                    "Example",
                    "Remote",
                    30,
                    90,
                    70,
                    84,
                    "Build OCaml services.",
                    "https://example.com/ocaml",
                    "OCaml.org jobs",
                    0,
                ),
            ],
        )

        strong_rows, other_rows = notify.get_notification_rows(connection)
        connection.close()

        self.assertEqual(
            [row[0] for row in strong_rows],
            ["Compiler Engineer", "OCaml Developer"],
        )
        self.assertEqual(other_rows, [])

    def test_filtering_happens_before_the_top_limit(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                score REAL,
                llm_score REAL,
                practicality_score REAL,
                final_score REAL,
                description TEXT,
                canonical_url TEXT,
                source TEXT,
                emailed INTEGER,
                posted_date TEXT,
                deadline TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO seen_items
                (id, title, final_score, score, description, canonical_url, source, emailed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    index,
                    "Quantitative Trader",
                    100 - index,
                    0,
                    "Trade markets. The company uses OCaml.",
                    f"https://example.com/trader/{index}",
                    "Jane Street",
                    0,
                )
                for index in range(1, 3)
            ]
            + [
                (
                    3,
                    "Compiler Engineer",
                    90,
                    0,
                    "Implement compiler infrastructure for OxCaml.",
                    "https://example.com/compiler",
                    "Jane Street",
                    0,
                )
            ],
        )

        with patch.object(notify, "TOP_N", 1):
            strong_rows, _ = notify.get_notification_rows(connection)
        connection.close()

        self.assertEqual([row[0] for row in strong_rows], ["Compiler Engineer"])

    def test_dry_run_neither_sends_nor_marks_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "agent.db"
            self._create_notification_database(
                database_path,
                [
                    (
                        1,
                        "OCaml Developer",
                        "Example",
                        "Remote",
                        30,
                        90,
                        80,
                        "Build OCaml services.",
                        "https://example.com/ocaml",
                        "OCaml.org jobs",
                        0,
                    )
                ],
            )

            output = io.StringIO()
            with (
                patch.object(notify, "DB_PATH", database_path),
                patch.object(sys, "argv", ["notify.py", "--dry-run"]),
                patch.object(notify, "send_long_message") as send,
                redirect_stdout(output),
            ):
                notify.main()

            connection = sqlite3.connect(database_path)
            emailed = connection.execute(
                "SELECT emailed FROM seen_items WHERE id = 1"
            ).fetchone()[0]
            connection.close()

        send.assert_not_called()
        self.assertEqual(emailed, 0)
        self.assertIn("Dry run complete", output.getvalue())

    def test_delivery_marks_all_included_rows_only_after_success(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "agent.db"
            self._create_notification_database(
                database_path,
                [
                    (
                        1,
                        "OCaml Developer",
                        "Example",
                        "Remote",
                        30,
                        90,
                        80,
                        "Build OCaml services.",
                        "https://example.com/strong",
                        "OCaml.org jobs",
                        0,
                    ),
                    (
                        2,
                        "Functional Programmer",
                        "Example",
                        "Remote",
                        30,
                        50,
                        50,
                        "Build functional software.",
                        "https://example.com/other",
                        "OCaml.org jobs",
                        0,
                    ),
                ],
            )

            with (
                patch.object(notify, "DB_PATH", database_path),
                patch.object(sys, "argv", ["notify.py"]),
                patch.object(notify, "send_long_message"),
            ):
                notify.main()

            connection = sqlite3.connect(database_path)
            emailed = connection.execute(
                "SELECT id, emailed FROM seen_items ORDER BY id"
            ).fetchall()
            connection.close()

        self.assertEqual(emailed, [(1, 1), (2, 1)])

    def test_failed_delivery_does_not_mark_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "agent.db"
            self._create_notification_database(
                database_path,
                [
                    (
                        1,
                        "OCaml Developer",
                        "Example",
                        "Remote",
                        30,
                        90,
                        80,
                        "Build OCaml services.",
                        "https://example.com/ocaml",
                        "OCaml.org jobs",
                        0,
                    )
                ],
            )

            with (
                patch.object(notify, "DB_PATH", database_path),
                patch.object(sys, "argv", ["notify.py"]),
                patch.object(
                    notify,
                    "send_long_message",
                    side_effect=RuntimeError("delivery failed"),
                ),
                self.assertRaisesRegex(RuntimeError, "delivery failed"),
            ):
                notify.main()

            connection = sqlite3.connect(database_path)
            emailed = connection.execute(
                "SELECT emailed FROM seen_items WHERE id = 1"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(emailed, 0)


if __name__ == "__main__":
    unittest.main()
