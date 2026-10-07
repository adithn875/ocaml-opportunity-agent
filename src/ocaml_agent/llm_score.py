"""LLM scoring stage using the local OmniRoute OpenAI-compatible API."""

import json
import os
import sqlite3
import urllib.request
from pathlib import Path

DB_PATH = Path("data/agent.db")
API_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1") + "/chat/completions"
API_KEY = os.environ["OMNIROUTE_API_KEY"]
MODEL = "auto/best-reasoning"


def score_job(job):
    prompt = f"""You are ranking job opportunities for an OCaml-focused engineer.

Evaluate this opportunity specifically for OCaml relevance.

Title: {job["title"]}
Company: {job["company"] or ""}
Location: {job["location"] or ""}

Description:
{job["description"] or ""}

Give:
1. A relevance score from 0 to 100.
2. A short explanation.

100 = exceptionally strong OCaml/compiler/programming-languages/formal-methods opportunity.
50 = meaningfully relevant but OCaml is not central.
0 = not meaningfully relevant to an OCaml-focused engineer.

Return ONLY valid JSON:
{{"score": <integer>, "reason": "<short explanation>"}}"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise technical job-ranking assistant.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 300,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())

    content = data["choices"][0]["message"]["content"].strip()

    # Models sometimes wrap JSON in markdown fences or add a short prefix.
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0].strip()

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Model did not return JSON: {content!r}")

    result = json.loads(content[start:end + 1])

    score = int(result["score"])
    if not 0 <= score <= 100:
        raise ValueError(f"Invalid LLM score: {score}")

    return score, str(result["reason"])


def main():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        jobs = connection.execute(
            """
            SELECT id, title, company, location, description
            FROM seen_items
            WHERE id IN (
                SELECT id
                FROM seen_items
                WHERE
                    score >= 30
                    AND NULLIF(TRIM(description), '') IS NOT NULL
                OR
                    lower(title) LIKE '%ocaml%'
                    OR lower(title) LIKE '%oxcaml%'
                    OR lower(title) LIKE '%compiler%'
                    OR lower(title) LIKE '%compilation%'
                    OR lower(title) LIKE '%formal method%'
                    OR lower(title) LIKE '%static analysis%'
                    OR lower(title) LIKE '%type system%'
            )
            ORDER BY score DESC, id
            """
        ).fetchall()

        print(f"LLM scoring {len(jobs)} candidates...")

        for job in jobs:
            score, reason = score_job(job)

            connection.execute(
                """
                UPDATE seen_items
                SET llm_score = ?, llm_reason = ?, llm_model = ?
                WHERE id = ?
                """,
                (score, reason, MODEL, job["id"]),
            )

            print(f'{job["id"]}: {score} - {job["title"]}')

        connection.commit()
        print("LLM scoring complete.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
