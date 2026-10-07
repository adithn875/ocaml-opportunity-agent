import json
import sqlite3
from pathlib import Path

from scrapling.fetchers import Fetcher


API_URL = (
    "https://api.getro.com/api/v2/collections/2502/search/jobs"
)

DB_PATH = Path("data/agent.db")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://careers.tezos.com",
    "Referer": "https://careers.tezos.com/",
}


def fetch_tezos_jobs():
    """Fetch current Tezos jobs from the Getro API."""

    response = Fetcher.post(
        API_URL,
        json={
            "hitsPerPage": 20,
            "page": 0,
            "filters": "",
            "query": "",
        },
        headers=HEADERS,
        timeout=30,
    )

    print("STATUS:", response.status)

    if response.status != 200:
        print("Request failed")
        return []

    data = json.loads(
        response.body.decode("utf-8")
    )

    results = data.get("results", {})

    jobs = results.get("jobs", [])
    count = results.get("count", 0)

    print("TOTAL JOBS:", count)
    print("JOBS RETURNED:", len(jobs))

    for job in jobs:
        print("\n---")
        print("TITLE:", job.get("title"))
        print("URL:", job.get("url"))
        print(
            "COMPANY:",
            job.get("organization", {}).get("name"),
        )
        print("LOCATION:", job.get("location"))

    return jobs


def save_jobs(jobs):
    """Save Tezos jobs into the existing SQLite database."""

    if not jobs:
        print("\nNo Tezos jobs to save.")
        return

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = sqlite3.connect(DB_PATH)

    inserted = 0
    skipped = 0

    for job in jobs:
        canonical_url = job.get("url")

        if not canonical_url:
            print("Skipping job without URL")
            continue

        cursor = con.execute(
            """
            INSERT OR IGNORE INTO seen_items (
                canonical_url,
                title,
                company,
                type,
                location,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                canonical_url,
                job.get("title"),
                job.get("organization", {}).get("name"),
                None,
                job.get("location"),
                "Tezos",
            ),
        )

        if cursor.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    con.commit()
    con.close()

    print(f"\nDATABASE INSERTED: {inserted}")
    print(f"DATABASE SKIPPED: {skipped}")


if __name__ == "__main__":
    jobs = fetch_tezos_jobs()

    print(f"\nCOLLECTED JOBS: {len(jobs)}")

    save_jobs(jobs)