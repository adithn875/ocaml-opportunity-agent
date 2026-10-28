import unittest
from unittest.mock import patch

from ocaml_agent.jane_street_collector import discover_jobs, is_ocaml_job


def job(position=None, overview=None, **extra):
    """Build a realistic Jane Street main.json record for filter tests."""

    record = {"id": 1001, "position": position, "overview": overview}
    record.update(extra)
    return record


class JaneStreetFilterTests(unittest.TestCase):
    def test_strong_title_signals_are_accepted(self):
        titles = (
            "OCaml Engineer",
            "OxCaml Educator",
            "Compiler Engineer",
            "Programming Language Engineer",
            "Type Systems Researcher",
            "Formal Methods Engineer",
            "Functional Programming Instructor",
        )

        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(is_ocaml_job(job(position=title)))

    def test_static_analysis_title_needs_programming_context(self):
        self.assertTrue(
            is_ocaml_job(
                job(
                    position="Static Analysis Engineer",
                    overview="Build static analysis tools for source code.",
                )
            )
        )
        self.assertFalse(
            is_ocaml_job(
                job(
                    position="Static Analysis Engineer",
                    overview="Analyze semiconductor timing and physical design.",
                )
            )
        )

    def test_substantive_overview_signals_are_accepted(self):
        examples = (
            job(
                position="Software Engineer",
                overview="Develop OxCaml compiler optimizations and infrastructure.",
            ),
            job(
                position="Research Engineer",
                overview="Research programming-language implementation and type inference.",
            ),
            job(
                position="R&D Engineer",
                overview="Build compiler tooling and language infrastructure.",
            ),
            job(
                position="Verification Engineer",
                overview="Apply formal verification to programs and compiler passes.",
            ),
            job(
                position="Software Engineer",
                overview="Build and maintain OCaml software systems for developers.",
            ),
        )

        for record in examples:
            with self.subTest(record=record):
                self.assertTrue(is_ocaml_job(record))

    def test_incidental_or_unrelated_roles_are_rejected(self):
        examples = (
            job(
                position="ASIC Engineer",
                overview=(
                    "Design ASICs. Our hardware toolchain is embedded in OCaml, "
                    "but this role focuses on physical design."
                ),
            ),
            job(
                position="Hardware Engineer",
                overview="Design FPGA systems and verify hardware components.",
            ),
            job(
                position="Network Engineer",
                overview="Operate low-latency network infrastructure.",
            ),
            job(
                position="Quantitative Trader",
                overview=(
                    "Develop trading strategies and manage risk. Jane Street "
                    "uses OCaml as its primary development language."
                ),
            ),
            job(
                position="Windows Engineer",
                overview="Support Windows hosts; the company also uses OCaml.",
            ),
            job(
                position="Software Engineer",
                overview=(
                    "Build reliable internal web services. We use OCaml as "
                    "our primary development language."
                ),
            ),
        )

        for record in examples:
            with self.subTest(record=record):
                self.assertFalse(is_ocaml_job(record))

    def test_explicit_programming_language_work_overrides_a_broad_title(self):
        self.assertTrue(
            is_ocaml_job(
                job(
                    position="Hardware Engineer",
                    overview="Implement compiler infrastructure for OxCaml.",
                )
            )
        )

    def test_metadata_is_not_used_as_a_relevance_signal(self):
        self.assertFalse(
            is_ocaml_job(
                job(
                    position="Operations Analyst",
                    overview="Coordinate daily accounting processes.",
                    team="OCaml Platform",
                    category="OCaml-related metadata",
                )
            )
        )

    def test_missing_or_malformed_optional_fields_are_handled_safely(self):
        malformed_records = (
            job(position="", overview=""),
            job(position=["OCaml Engineer"], overview="Build compilers."),
            job(position="Engineer", overview={"text": "OCaml"}),
            {"position": "Engineer", "overview": None},
            None,
        )

        for record in malformed_records:
            with self.subTest(record=record):
                self.assertFalse(is_ocaml_job(record))

        self.assertTrue(
            is_ocaml_job(
                job(position=None, overview="Build compiler infrastructure.")
            )
        )
        self.assertTrue(is_ocaml_job(job(position="Compiler Engineer")))

    def test_optional_description_is_supported_without_metadata_scanning(self):
        self.assertTrue(
            is_ocaml_job(
                job(
                    position="Engineer",
                    overview=None,
                    description="Implement OCaml software systems for developers.",
                )
            )
        )

    def test_matching_is_case_insensitive(self):
        self.assertTrue(
            is_ocaml_job(
                job(
                    position="engineer",
                    overview="BUILD OXCAML COMPILER INFRASTRUCTURE.",
                )
            )
        )


class JaneStreetDiscoveryTests(unittest.TestCase):
    @patch("ocaml_agent.jane_street_collector.fetch_json")
    def test_discover_jobs_uses_active_position_ids(self, mock_fetch_json):
        mock_fetch_json.side_effect = [
            [
                job(position="Compiler Engineer", id=1),
                job(position="Network Engineer", id=2),
            ],
            [1],
        ]

        active_jobs = discover_jobs()

        self.assertEqual([record["id"] for record in active_jobs], [1])


if __name__ == "__main__":
    unittest.main()
