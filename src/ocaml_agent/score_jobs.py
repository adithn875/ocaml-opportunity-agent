import json
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
        [str(OCAML_SCORER), "--json"],
        input=input_data,
        text=True,
        capture_output=True,
        check=True,
    )

    try:
        payload = json.loads(result.stdout)
        score = payload["score"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise RuntimeError("OCaml scorer did not return valid JSON with a score") from exc

    if not isinstance(score, int) or isinstance(score, bool):
        raise RuntimeError("OCaml scorer returned a non-integer score")

    return score


def get_jobs(connection):
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT id, title, company, location, description
        FROM seen_items
        WHERE score IS NULL
        ORDER BY id
        """
    ).fetchall()


def save_score(connection, job_id, score):
    connection.execute(
        "UPDATE seen_items SET score = ? WHERE id = ? AND score IS NULL",
        (score, job_id),
    )


def main():
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


if __name__ == "__main__":
    main()
