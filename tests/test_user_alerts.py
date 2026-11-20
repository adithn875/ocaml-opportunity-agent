import unittest
from datetime import UTC, datetime, timedelta

from ocaml_agent import user_alerts


class UserAlertTests(unittest.TestCase):
    def test_due_frequency_respects_daily_and_weekly_preferences(self):
        current_time = datetime(2026, 11, 20, 12, tzinfo=UTC)
        yesterday = (current_time - timedelta(days=1, minutes=1)).isoformat()
        recent = (current_time - timedelta(hours=1)).isoformat()

        self.assertTrue(user_alerts.is_due({"last_checked_at": yesterday}, "daily", current_time))
        self.assertFalse(user_alerts.is_due({"last_checked_at": recent}, "daily", current_time))
        self.assertFalse(user_alerts.is_due({"last_checked_at": yesterday}, "weekly", current_time))

    def test_profile_matching_uses_score_skills_location_and_remote_preference(self):
        job = {
            "title": "OCaml Compiler Engineer",
            "description": "Work on compiler infrastructure.",
            "location": "Remote Europe",
            "remote": "remote-worldwide",
            "final_score": 86,
        }
        profile = {
            "skills": ["OCaml", "compiler"],
            "locations": ["Europe"],
            "remote_preference": "remote",
            "minimum_score": 80,
        }

        self.assertTrue(user_alerts.matches_profile(job, profile, 70))
        self.assertFalse(user_alerts.matches_profile(job, profile, 90))
        self.assertFalse(user_alerts.matches_profile(job, {**profile, "skills": ["Rust"]}, 70))

    def test_build_alert_lists_the_original_job_url(self):
        message = user_alerts.build_alert([
            {
                "title": "OCaml Engineer",
                "company": "Example",
                "location": "Remote",
                "final_score": 88,
                "source_url": "https://example.com/jobs/1",
            }
        ])

        self.assertIn("OCaml Engineer", message)
        self.assertIn("https://example.com/jobs/1", message)
