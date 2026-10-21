import unittest

from ocaml_agent.notify import build_message


class NotificationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
