"""Deterministic filtering for opportunities eligible for later ranking."""

from dataclasses import dataclass
import sqlite3
from typing import Mapping, Sequence


SCORE_THRESHOLD = 30

# These cues are deliberately limited to the deterministic scorer's technical
# vocabulary. They allow clearly relevant title-only records through when a
# source cannot provide a description.
STRONG_TITLE_SIGNALS = (
    ("OCaml", "ocaml"),
    ("OxCaml", "oxcaml"),
    ("Compiler", "compiler"),
    ("Compilation", "compilation"),
    ("Dune", "dune"),
    ("opam", "opam"),
    ("Functional programming", "functional programming"),
    ("Programming languages", "programming language"),
    ("Type systems", "type system"),
    ("Static analysis", "static analysis"),
    ("Formal verification", "formal verification"),
    ("Formal methods", "formal methods"),
    ("OCaml ecosystem", "ocaml ecosystem"),
)


@dataclass(frozen=True)
class CandidateDecision:
    """An explainable decision for one stored opportunity."""

    accepted: bool
    reason: str
    title_signals: tuple[str, ...]
    description: str | None = None


@dataclass(frozen=True)
class Candidate:
    """The stable, derived record passed to a future ranking stage."""

    id: int
    title: str
    company: str | None
    score: float
    reason: str
    title_signals: tuple[str, ...]
    description: str | None


def has_description(job: Mapping[str, object]) -> bool:
    """Return whether a job has meaningful source text."""

    description = job.get("description")
    return isinstance(description, str) and bool(description.strip())


def title_signals(title: str | None) -> tuple[str, ...]:
    """Return explicit OCaml-relevant concepts present in a title."""

    normalized = (title or "").casefold()
    return tuple(
        name
        for name, phrase in STRONG_TITLE_SIGNALS
        if phrase in normalized
    )


def is_non_opportunity_title(title: str | None) -> bool:
    """Exclude known announcement and aggregate-list formats from candidates."""

    normalized = (title or "").casefold().strip()
    return normalized.startswith("[ann]") or normalized.startswith("awesome ")


def decide(job: Mapping[str, object]) -> CandidateDecision:
    """Apply the deterministic candidate policy to one database record."""

    title = job.get("title")
    normalized_title = title if isinstance(title, str) else ""
    signals = title_signals(normalized_title)
    score = float(job.get("score") or 0)

    if is_non_opportunity_title(normalized_title):
        return CandidateDecision(
            accepted=False,
            reason="title identifies an announcement or aggregate job list",
            title_signals=signals,
        )

    if signals:
        return CandidateDecision(
            accepted=True,
            reason="explicit OCaml-relevant title signal: " + ", ".join(signals),
            title_signals=signals,
        )

    if score >= SCORE_THRESHOLD and has_description(job):
        return CandidateDecision(
            accepted=True,
            reason=(
                f"score {score:g} meets the {SCORE_THRESHOLD}-point threshold "
                "with a source description"
            ),
            title_signals=signals,
        )

    if score >= SCORE_THRESHOLD:
        reason = (
            f"score {score:g} has no description or explicit OCaml-relevant "
            "title signal"
        )
    elif score > 0:
        reason = (
            f"score {score:g} is below the {SCORE_THRESHOLD}-point threshold "
            "without an explicit title signal"
        )
    else:
        reason = "no deterministic OCaml-relevance evidence"

    return CandidateDecision(
        accepted=False,
        reason=reason,
        title_signals=signals,
    )


def get_candidates(connection: sqlite3.Connection) -> list[Candidate]:
    """Return a stable, score-ranked candidate set without changing SQLite."""

    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, title, company, score, description
        FROM seen_items
        ORDER BY id
        """
    ).fetchall()

    candidates = []
    for row in rows:
        values = dict(row)
        decision = decide(values)
        if decision.accepted:
            candidates.append(
                Candidate(
                    id=values["id"],
                    title=values["title"],
                    company=values["company"],
                    score=float(values["score"] or 0),
                    reason=decision.reason,
                    title_signals=decision.title_signals,
                    description=values["description"],
                )
            )

    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.id))


def main() -> None:
    """Print the current derived candidate set for inspection."""

    connection = sqlite3.connect("data/agent.db")
    try:
        candidates = get_candidates(connection)
    finally:
        connection.close()

    print(f"Candidates: {len(candidates)}")
    for candidate in candidates:
        company = candidate.company or "Unknown company"
        print(
            f"{candidate.id}\t{candidate.score:g}\t{candidate.title}\t"
            f"{company}\t{candidate.reason}"
        )


if __name__ == "__main__":
    main()
