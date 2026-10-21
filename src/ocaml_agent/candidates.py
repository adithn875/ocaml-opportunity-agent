"""Deterministic filtering for opportunities eligible for later ranking."""

from dataclasses import dataclass
import sqlite3
from typing import Mapping

from .ocaml_candidates import evaluate_candidate


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
    """Return OCaml-evaluated relevance signals present in a title."""

    decision = evaluate_candidate({"title": title})
    return tuple(decision["title_signals"])


def is_non_opportunity_title(title: str | None) -> bool:
    """Exclude known announcement and aggregate-list formats from candidates."""

    decision = evaluate_candidate({"title": title})
    return (
        decision["reason"]
        == "title identifies an announcement or aggregate job list"
    )


def decide(job: Mapping[str, object]) -> CandidateDecision:
    """Apply the OCaml deterministic candidate policy to one database record."""

    decision = evaluate_candidate(job)
    return CandidateDecision(
        accepted=decision["accepted"],
        reason=decision["reason"],
        title_signals=tuple(decision["title_signals"]),
    )


def get_candidates(connection: sqlite3.Connection) -> list[Candidate]:
    """Return a stable, score-ranked candidate set without changing SQLite."""

    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT id, title, company, score, description, source
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
