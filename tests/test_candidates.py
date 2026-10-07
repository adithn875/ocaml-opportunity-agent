import unittest

from ocaml_agent.candidates import decide


def job(*, title, score, description=None):
    return {
        "title": title,
        "score": score,
        "description": description,
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


if __name__ == "__main__":
    unittest.main()
