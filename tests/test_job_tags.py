import unittest

from ocaml_agent.job_tags import derive_tags


class JobTagTests(unittest.TestCase):
    def test_uses_explicit_evidence_for_specialist_tags(self):
        tags = derive_tags(
            "OCaml compiler engineer",
            "Build static analysis and type inference tooling for a compiler.",
        )

        self.assertEqual(
            tags,
            ["OCaml", "Compilers", "Type systems", "Static analysis"],
        )

    def test_does_not_add_tags_without_evidence(self):
        self.assertEqual(derive_tags("Software engineer", "Build web services."), [])
