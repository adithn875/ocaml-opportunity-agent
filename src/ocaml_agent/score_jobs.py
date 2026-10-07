import re
import sqlite3
import subprocess
from pathlib import Path

DB_PATH = Path("data/agent.db")
OCAML_SCORER = (
    Path("ocaml-scoring")
    / "ocaml_scoring"
    / "_build"
    / "default"
    / "bin"
    / "main.exe"
)


def score_job(job):
    description = job["description"] or ""

    input_data = "\n".join(
        [
            job["title"] or "",
            job["company"] or "",
            job["location"] or "",
            description,
        ]
    ) + "\n"

    result = subprocess.run(
        [str(OCAML_SCORER)],
        input=input_data,
        text=True,
        capture_output=True,
        check=True,
    )

    match = re.search(r"Score: (\d+)", result.stdout)

    if not match:
        raise RuntimeError("OCaml scorer did not return a score")

    return int(match.group(1))


def get_jobs(connection):
    connection.row_factory = sqlite3.Row

    return connection.execute(
        """
        SELECT
            id,
            title,
            company,
            location,
            description
        FROM seen_items
        ORDER BY id
        """
    ).fetchall()


def save_score(connection, job_id, score):
    connection.execute(
        "UPDATE seen_items SET score = ? WHERE id = ?",
        (score, job_id),
    )


if __name__ == "__main__":
    connection = sqlite3.connect(DB_PATH)

    try:
        jobs = get_jobs(connection)

        print(f"Scoring {len(jobs)} jobs...")

        for job in jobs:
            score = score_job(job)
            save_score(connection, job["id"], score)

        connection.commit()

        print("Scoring complete.")

    finally:
        connection.close()
