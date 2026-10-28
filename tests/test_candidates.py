import sqlite3
import unittest

from ocaml_agent.candidates import decide, get_candidates


def job(*, title, score, description=None, source=None):
    return {
        "title": title,
        "score": score,
        "description": description,
        "source": source,
    }


class CandidateFilterTests(unittest.TestCase):
    def test_high_score_job_with_description_is_accepted(self):
        decision = decide(
            job(
                title="Research Engineer",
                score=45,
                description="Work on static analysis tooling in OCaml.",
            )
        )

        self.assertTrue(decision.accepted)
        self.assertIn("threshold", decision.reason)

    def test_borderline_compiler_job_is_accepted_by_title(self):
        decision = decide(
            job(
                title="Compiler Engineer",
                score=25,
                description="Build language tooling.",
            )
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.title_signals, ("Compiler",))

    def test_zero_score_generic_job_is_rejected(self):
        decision = decide(
            job(
                title="Frontend Engineer",
                score=0,
                description="Build web applications.",
            )
        )

        self.assertFalse(decision.accepted)

    def test_ocaml_title_without_description_is_accepted(self):
        decision = decide(
            job(title="OCaml Developer", score=0)
        )

        self.assertTrue(decision.accepted)
        self.assertEqual(decision.title_signals, ("OCaml",))

    def test_generic_title_with_source_only_score_is_rejected(self):
        decision = decide(
            job(title="Software Engineer", score=30)
        )

        self.assertFalse(decision.accepted)
        self.assertIn("no description", decision.reason)

    def test_announcement_with_a_strong_signal_is_rejected(self):
        decision = decide(
            job(
                title="[ANN] HOL Light released to OPAM",
                score=15,
                description="A package announcement.",
            )
        )

        self.assertFalse(decision.accepted)


    def test_jane_street_listing_with_substantive_evidence_is_accepted(self):
        decision = decide(
            job(
                title="Compiler Engineer",
                score=0,
                description="Implement compiler infrastructure for OxCaml.",
                source="Jane Street",
            )
        )
        self.assertTrue(decision.accepted)

    def test_jane_street_incidental_ocaml_listing_is_rejected(self):
        decision = decide(
            job(
                title="Quantitative Trader",
                score=60,
                description=(
                    "Trade markets. Jane Street uses OCaml as its primary "
                    "development language."
                ),
                source="Jane Street",
            )
        )

        self.assertFalse(decision.accepted)
        self.assertIn("lacks substantive", decision.reason)

    def test_jane_street_listing_without_description_is_rejected(self):
        decision = decide(
            job(title="Front End Software Engineer", score=0, source="Jane Street")
        )
        self.assertFalse(decision.accepted)

    def test_ocaml_org_listing_without_description_is_accepted(self):
        decision = decide(
            job(title="Cryptography Engineer", score=0, source="OCaml.org jobs")
        )
        self.assertTrue(decision.accepted)

    def test_spontaneous_application_is_rejected(self):
        decision = decide(
            job(
                title="Spontaneous Application",
                score=30,
                source="OCaml.org jobs",
            )
        )
        self.assertFalse(decision.accepted)

    def test_ocaml_discuss_job_with_description_is_accepted(self):
        decision = decide(
            job(
                title="Research Internship",
                score=0,
                description="Work on OCaml and formal verification.",
                source="OCaml Discuss Jobs",
            )
        )
        self.assertTrue(decision.accepted)

    def test_aggregate_job_list_is_rejected(self):
        decision = decide(
            job(
                title="Awesome Functional Programming Jobs",
                score=15,
                description="A list of jobs.",
                source="OCaml Discuss Jobs",
            )
        )
        self.assertFalse(decision.accepted)

    def test_candidate_query_preserves_source_specific_rules(self):
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE seen_items (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT,
                score REAL,
                description TEXT,
                source TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO seen_items (id, title, score, description, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "Compiler Engineer",
                    0,
                    "Implement compiler infrastructure for OxCaml.",
                    "Jane Street",
                ),
                (2, "Cryptography Engineer", 0, None, "OCaml.org jobs"),
            ],
        )

        try:
            candidates = get_candidates(connection)
        finally:
            connection.close()

        self.assertEqual([candidate.id for candidate in candidates], [1, 2])
        self.assertEqual(
            candidates[0].reason,
            "jane street listing has a description for LLM review",
        )
        self.assertEqual(
            candidates[1].reason,
            "OCaml.org Jobs listing eligible for LLM review",
        )


if __name__ == "__main__":
    unittest.main()
