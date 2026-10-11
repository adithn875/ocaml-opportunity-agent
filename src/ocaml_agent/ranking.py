
"""Final ranking for OCaml opportunities."""

import argparse
import sqlite3
from pathlib import Path

TECHNICAL_WEIGHT = 0.70
PRACTICALITY_WEIGHT = 0.30
DB_PATH = Path("data/agent.db")


def calculate_final_score(
    *,
    technical_score: float,
    practicality_score: float,
) -> float:
    """Calculate a final score from technical fit and practicality."""
    for name, score in (
        ("technical_score", technical_score),
        ("practicality_score", practicality_score),
    ):
        if not 0 <= score <= 100:
            raise ValueError(f"{name} must be between 0 and 100")

    return (
        TECHNICAL_WEIGHT * technical_score
        + PRACTICALITY_WEIGHT * practicality_score
    )


def rank_unscored(connection: sqlite3.Connection, *, dry_run: bool = True) -> int:
    """Rank eligible rows without replacing existing final scores."""
    rows = connection.execute(
        """
        SELECT id, llm_score, practicality_score
        FROM seen_items
        WHERE final_score IS NULL
          AND llm_score BETWEEN 0 AND 100
          AND practicality_score BETWEEN 0 AND 100
        ORDER BY id
        """
    ).fetchall()

    for row_id, technical, practicality in rows:
        final_score = calculate_final_score(
            technical_score=technical,
            practicality_score=practicality,
        )
        print(f"{row_id}: {final_score:.1f}")

        if not dry_run:
            connection.execute(
                """
                UPDATE seen_items
                SET final_score = ?
                WHERE id = ? AND final_score IS NULL
                """,
                (final_score, row_id),
            )

    if not dry_run:
        connection.commit()

    print(f"{'Would rank' if dry_run else 'Ranked'} {len(rows)} opportunities.")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate final opportunity scores.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Save scores to SQLite. Without this flag, only preview changes.",
    )
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()

    with sqlite3.connect(args.db) as connection:
        rank_unscored(connection, dry_run=not args.write)


if __name__ == "__main__":
    main()
