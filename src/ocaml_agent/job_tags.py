"""Deterministic, explainable technology and domain tags for opportunities."""

import re


TAG_PATTERNS = (
    ("OCaml", (r"\bocaml\b", r"\boxcaml\b")),
    ("Functional programming", (r"\bfunctional programming\b",)),
    ("Compilers", (r"\bcompilers?\b", r"\bcompiler tooling\b", r"\bmlir\b", r"\bllvm\b")),
    ("Programming languages", (r"\bprogramming languages?\b", r"\blanguage implementation\b")),
    ("Type systems", (r"\btype systems?\b", r"\btype inference\b")),
    ("Formal methods", (r"\bformal methods?\b",)),
    ("Program verification", (r"\bprogram verification\b", r"\bformal verification\b")),
    ("Static analysis", (r"\bstatic analysis\b", r"\bprogram analysis\b")),
    ("Theorem proving", (r"\btheorem proving\b", r"\bproof assistants?\b", r"\bautomated reasoning\b")),
    ("Lean", (r"\blean ?4?\b",)),
    ("Rocq / Coq", (r"\b(?:rocq|coq)\b",)),
    ("Isabelle", (r"\bisabelle\b",)),
    ("SMT", (r"\b(?:smt|z3)\b",)),
)


def derive_tags(title, description):
    """Return stable domain tags supported by a listing's title or description."""
    text = "\n".join(value for value in (title, description) if value)
    return [
        tag
        for tag, patterns in TAG_PATTERNS
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    ]
