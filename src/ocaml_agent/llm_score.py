"""LLM scoring stage using the local OmniRoute OpenAI-compatible API."""

import json
import os
import sqlite3
import urllib.request
from pathlib import Path

DB_PATH = Path("data/agent.db")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "omniroute").lower()

if LLM_PROVIDER == "groq":
    API_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1") + "/chat/completions"
    API_KEY = os.environ["GROQ_API_KEY"]
    MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
elif LLM_PROVIDER == "omniroute":
    API_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1") + "/chat/completions"
    API_KEY = os.environ["OMNIROUTE_API_KEY"]
    MODEL = os.getenv("OMNIROUTE_MODEL", "auto/best-reasoning")
else:
    raise ValueError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")


def score_job(job):
    prompt = f"""You are ranking job opportunities for an OCaml-focused engineer.

Evaluate this opportunity in TWO independent dimensions.

Title: {job["title"]}
Company: {job["company"] or ""}
Location: {job["location"] or ""}

Description:
{job["description"] or ""}

DIMENSION 1 — TECHNICAL OCAML RELEVANCE

Give a technical relevance score from 0 to 100.

100 = exceptionally strong OCaml/compiler/programming-languages/formal-methods opportunity.
50 = meaningfully relevant but OCaml is not central.
0 = not meaningfully relevant to an OCaml-focused engineer.

DIMENSION 2 — PRACTICAL FIT

Give a practicality score from 0 to 100 based ONLY on evidence in the supplied job information.

Consider:
- stated seniority or experience requirements
- whether the role is internship, junior, graduate, or experienced
- required technical background
- how directly the stated requirements fit an OCaml-focused early-career engineer
- unusually specialized requirements

Do NOT estimate a probability of getting an interview.
Do NOT penalize a company simply because it is famous or competitive.
If the description does not provide enough evidence, use a neutral practicality score around 70. Missing information is NOT evidence of poor fit. Never assume seniority, experience requirements, or difficulty when they are not explicitly stated.

CLASSIFICATION

Choose exactly one:
- "Target" = strong technical match and reasonably practical
- "Good Fit" = good match with manageable requirements
- "Reach" = excellent opportunity but requirements appear demanding or highly specialized
- "Low Fit" = significant mismatch or weak practical fit

Return ONLY valid JSON:
{{"technical_score": <integer>, "practicality_score": <integer>, "classification": "<Target|Good Fit|Reach|Low Fit>", "technical_reason": "<short explanation>", "practicality_reason": "<short explanation>"}}"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise technical job-ranking assistant. Do not invent requirements that are not present in the job description.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 500,
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "curl/8.7.1",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())

    content = data["choices"][0]["message"]["content"].strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        content = content.rsplit("```", 1)[0].strip()

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Model did not return JSON: {content!r}")

    result = json.loads(content[start:end + 1])

    technical_score = int(result["technical_score"])
    practicality_score = int(result["practicality_score"])

    if not 0 <= technical_score <= 100:
        raise ValueError(f"Invalid technical score: {technical_score}")

    if not 0 <= practicality_score <= 100:
        raise ValueError(f"Invalid practicality score: {practicality_score}")

    classification = str(result["classification"])
    allowed = {"Target", "Good Fit", "Reach", "Low Fit"}

    if classification not in allowed:
        raise ValueError(f"Invalid classification: {classification}")

    return (
        technical_score,
        practicality_score,
        classification,
        str(result["technical_reason"]),
        str(result["practicality_reason"]),
    )


def main():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    try:
        jobs = connection.execute(
            """
            SELECT id, title, company, location, description, score
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
            try:
                technical_score, practicality_score, classification, technical_reason, practicality_reason = score_job(job)
            except (ValueError, KeyError, TypeError) as error:
                print(f'RETRY {job["id"]}: {job["title"]} - invalid LLM response')
                try:
                    technical_score, practicality_score, classification, technical_reason, practicality_reason = score_job(job)
                except (ValueError, KeyError, TypeError) as retry_error:
                    print(f'FALLBACK {job["id"]}: {job["title"]} - using neutral practicality score')
                    technical_score = int(job["score"] or 0)
                    practicality_score = 70
                    classification = "Good Fit"
                    technical_reason = "LLM response could not be parsed; deterministic OCaml relevance retained."
                    practicality_reason = "Neutral fallback because the model did not return a valid practicality score."

            connection.execute(
                """
                UPDATE seen_items
                SET llm_score = ?,
                    llm_reason = ?,
                    llm_model = ?,
                    practicality_score = ?,
                    opportunity_class = ?,
                    practicality_reason = ?
                WHERE id = ?
                """,
                (technical_score, technical_reason, MODEL, practicality_score, classification, practicality_reason, job["id"]),
            )
            connection.commit()

            print(f'{job["id"]}: {technical_score} / {practicality_score} - {job["title"]}')

        print("LLM scoring complete.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
