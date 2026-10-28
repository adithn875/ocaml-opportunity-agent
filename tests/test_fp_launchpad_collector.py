import unittest

from ocaml_agent.fp_launchpad_collector import (
    extract_category,
    extract_date,
    is_relevant,
    normalize_url,
)


class FPLaunchpadCollectorTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_parameters(self):
        self.assertEqual(
            normalize_url(
                "https://www.fplaunchpad.org/updates/example/"
                "?utm_source=test&fbclid=abc#section"
            ),
            "https://fplaunchpad.org/updates/example/",
        )

    def test_normalize_url_rejects_external_hosts(self):
        self.assertIsNone(
            normalize_url("https://example.com/updates/example/")
        )

    def test_normalize_url_rejects_non_http_schemes(self):
        self.assertIsNone(normalize_url("mailto:hello@example.com"))

    def test_extract_category_finds_known_category(self):
        self.assertEqual(
            extract_category("Some announcement title\nEvent\nDetails"),
            "event",
        )

    def test_extract_date_supports_visible_date_formats(self):
        self.assertEqual(
            extract_date("Applications close on 24 September 2026."),
            "24 September 2026",
        )
        self.assertEqual(
            extract_date("Published 2026-09-24"),
            "2026-09-24",
        )

    def test_announcement_requires_an_opportunity_signal(self):
        self.assertTrue(
            is_relevant(
                "Summer Internship Applications Open",
                "announcement",
                "Applications are open for the summer internship.",
            )
        )
        self.assertFalse(
            is_relevant(
                "FPL Reading: Recent Articles",
                "announcement",
                "A roundup of recent functional programming articles.",
            )
        )

    def test_event_categories_are_relevant(self):
        for category in ("event", "talk", "seminar", "workshop", "conference"):
            with self.subTest(category=category):
                self.assertTrue(
                    is_relevant("FP Meetup", category, "Join the community.")
                )


if __name__ == "__main__":
    unittest.main()


class FPLaunchpadSafetyTests(unittest.TestCase):
    def test_http_failure_raises_without_collecting(self):
        from unittest.mock import Mock, patch

        from ocaml_agent import fp_launchpad_collector as collector

        response = Mock(status=503)

        with patch.object(collector.Fetcher, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "HTTP 503"):
                collector.fetch_updates()

    def test_upsert_preserves_existing_score_and_notification_state(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from ocaml_agent import fp_launchpad_collector as collector
        from ocaml_agent.db import SCHEMA

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "test.db"

            with sqlite3.connect(database_path) as connection:
                connection.executescript(SCHEMA)
                connection.execute(
                    """
                    INSERT INTO seen_items (
                        canonical_url, title, company, source,
                        score, emailed, description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "https://fplaunchpad.org/updates/example/",
                        "Original title",
                        "FP Launchpad",
                        "FP Launchpad",
                        88,
                        1,
                        "Short description",
                    ),
                )

            updated_opportunity = {
                "url": "https://fplaunchpad.org/updates/example/",
                "title": "Updated title",
                "company": "FP Launchpad",
                "type": "event",
                "source": "FP Launchpad",
                "description": "A longer, more detailed description.",
            }

            with patch.object(collector, "DB_PATH", database_path):
                collector.save_opportunities([updated_opportunity])

            with sqlite3.connect(database_path) as connection:
                row = connection.execute(
                    """
                    SELECT title, score, emailed, description
                    FROM seen_items
                    WHERE canonical_url = ?
                    """,
                    (updated_opportunity["url"],),
                ).fetchone()

        self.assertEqual(row[0], "Original title")
        self.assertEqual(row[1], 88)
        self.assertEqual(row[2], 1)
        self.assertEqual(row[3], "A longer, more detailed description.")
