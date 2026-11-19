import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
