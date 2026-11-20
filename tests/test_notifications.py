import unittest
from datetime import UTC, datetime, timedelta

from ocaml_agent import notifications


class NotificationTests(unittest.TestCase):
    def test_candidates_only_include_new_profile_matches(self):
        current_time = datetime(2026, 11, 20, 12, tzinfo=UTC)
        jobs = [
            {
                "id": 1,
                "title": "OCaml Compiler Engineer",
                "description": "Compiler tooling",
                "remote": "remote-worldwide",
                "final_score": 90,
                "first_seen": (current_time - timedelta(minutes=5)).isoformat(),
            },
            {
                "id": 2,
                "title": "Old OCaml role",
                "description": "OCaml",
                "remote": "remote-worldwide",
                "final_score": 90,
                "first_seen": (current_time - timedelta(days=2)).isoformat(),
            },
        ]
        profile = {
            "skills": ["OCaml"],
            "locations": [],
            "remote_preference": "remote",
            "minimum_score": 70,
        }

        matches = notifications.notification_candidates(
            jobs, current_time - timedelta(hours=1), profile, 70
        )

        self.assertEqual([job["id"] for job in matches], [1])
