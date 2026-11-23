import json
from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from ocaml_agent import db, supabase_sync


class SupabaseSyncTests(unittest.TestCase):
    def test_load_jobs_maps_the_local_schema_to_the_public_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"
            with db.connect(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO seen_items (
                        canonical_url, title, company, type, source,
                        score, llm_score, final_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "https://example.com/jobs/1",
                        "OCaml Engineer",
                        "Example",
                        "full-time",
                        "Example Careers",
                        85,
                        90,
                        86.5,
                    ),
                )

            jobs = supabase_sync.load_jobs(database_path)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["source_url"], "https://example.com/jobs/1")
        self.assertEqual(jobs[0]["employment_type"], "full-time")
        self.assertEqual(jobs[0]["final_score"], 86.5)
        self.assertIsNotNone(jobs[0]["last_seen_at"])

    def test_load_source_runs_generates_a_stable_upsert_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.db"
            with db.connect(database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO source_runs (
                        source, duration_seconds, status, new_items, error
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    ("Example", 1.5, "failed", 0, "source unavailable"),
                )

            source_runs = supabase_sync.load_source_runs(database_path)

        self.assertEqual(len(source_runs), 1)
        self.assertEqual(source_runs[0]["source_run_key"], "local:1")
        self.assertEqual(source_runs[0]["status"], "failed")

    @patch("ocaml_agent.supabase_sync.request.urlopen")
    def test_upload_jobs_posts_an_upsert_request(self, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.status = 201
        jobs = [{"source_url": "https://example.com/jobs/1", "title": "OCaml"}]

        supabase_sync.upload_jobs("https://project.supabase.co", "secret", jobs)

        upload_request = mock_urlopen.call_args.args[0]
        self.assertEqual(
            upload_request.full_url,
            "https://project.supabase.co/rest/v1/jobs?on_conflict=source_url",
        )
        self.assertEqual(json.loads(upload_request.data), jobs)
        self.assertEqual(upload_request.get_header("Prefer"), "resolution=merge-duplicates,return=minimal")

    @patch("ocaml_agent.supabase_sync.request.urlopen")
    def test_upload_source_runs_uses_the_source_run_key(self, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.status = 201
        runs = [{"source_run_key": "Example:2026-01-01", "source": "Example"}]

        supabase_sync.upload_source_runs("https://project.supabase.co", "secret", runs)

        upload_request = mock_urlopen.call_args.args[0]
        self.assertEqual(
            upload_request.full_url,
            "https://project.supabase.co/rest/v1/source_runs?on_conflict=source_run_key",
        )

    @patch("ocaml_agent.supabase_sync.request.urlopen")
    def test_upload_error_includes_the_supabase_response_body(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://project.supabase.co/rest/v1/jobs",
            400,
            "Bad Request",
            None,
            BytesIO(b'{"message":"column jobs.deadline does not exist"}'),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "column jobs.deadline does not exist",
        ):
            supabase_sync.upload_jobs(
                "https://project.supabase.co",
                "secret",
                [{"source_url": "https://example.com/jobs/1", "title": "OCaml"}],
            )

    @patch("ocaml_agent.supabase_sync.time.sleep")
    @patch("ocaml_agent.supabase_sync.request.urlopen")
    def test_upload_retries_a_temporary_supabase_failure(self, mock_urlopen, mock_sleep):
        retry_error = HTTPError(
            "https://project.supabase.co/rest/v1/jobs",
            503,
            "Unavailable",
            None,
            BytesIO(b'{"message":"temporarily unavailable"}'),
        )
        response = MagicMock()
        response.__enter__.return_value.status = 201
        mock_urlopen.side_effect = [retry_error, response]

        supabase_sync.upload_jobs(
            "https://project.supabase.co",
            "secret",
            [{"source_url": "https://example.com/jobs/1", "title": "OCaml"}],
        )

        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("ocaml_agent.supabase_sync.request.urlopen")
    def test_schema_validation_lists_all_missing_columns(self, mock_urlopen):
        def open_request(schema_request, timeout):
            if "select=source&" in schema_request.full_url:
                raise HTTPError(
                    schema_request.full_url,
                    400,
                    "Bad Request",
                    None,
                    BytesIO(b'{"code":"PGRST204"}'),
                )
            response = MagicMock()
            response.__enter__.return_value.status = 200
            return response

        mock_urlopen.side_effect = open_request

        with self.assertRaisesRegex(
            RuntimeError,
            "Supabase jobs is missing required columns: source",
        ):
            supabase_sync.validate_table_columns(
                "https://project.supabase.co",
                "secret",
                "jobs",
                ("title", "source", "description"),
            )
