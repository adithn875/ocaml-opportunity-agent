"""
OCaml Opportunity Agent - Collector

Milestone 2:
Collect jobs from OCaml.org and store them in SQLite.

Current pipeline:

OCaml.org YAML
      ↓
Scrapling
      ↓
YAML parsing
      ↓
Normalize job
      ↓
SQLite
"""

from pathlib import Path
import sqlite3

import yaml
from scrapling.fetchers import Fetcher


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

SOURCES_FILE = ROOT / "config" / "sources.yaml"
DATABASE_FILE = ROOT / "data" / "agent.db"


# ---------------------------------------------------------
# Load source configuration
# ---------------------------------------------------------

def load_ocaml_source():
    """Find the OCaml.org jobs source in sources.yaml."""

    with open(SOURCES_FILE, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    for source in config.get("aggregators", []):
        if source.get("name") == "OCaml.org jobs":
            return source

    raise ValueError(
        "OCaml.org jobs source was not found in sources.yaml"
    )


# ---------------------------------------------------------
# Fetch jobs
# ---------------------------------------------------------

def fetch_jobs(source):
    """Download the OCaml.org jobs YAML file using Scrapling."""

    url = source.get("api", source["url"])

    print(f"Fetching: {url}")

    response = Fetcher.get(
        url,
        timeout=30,
    )

    if response.status != 200:
        raise RuntimeError(
            f"Failed to fetch jobs: HTTP {response.status}"
        )

    # The raw YAML is available as bytes.
    return response.body


# ---------------------------------------------------------
# Normalize one job
# ---------------------------------------------------------

def normalize_job(job):
    """
    Convert an OCaml.org job into our database format.
    """

    locations = job.get("locations") or []

    # Convert:
    # ['France', 'Paris']
    #
    # into:
    # "France; Paris"
    location = "; ".join(locations)

    return {
        "canonical_url": job.get("link"),
        "title": job.get("title"),
        "company": job.get("company"),
        "type": None,
        "location": location,
        "remote": None,
        "posted_date": job.get("publication_date"),
        "deadline": None,
        "source": "OCaml.org jobs",
        "score": None,
    }


# ---------------------------------------------------------
# Save jobs to SQLite
# ---------------------------------------------------------

def save_jobs(jobs):
    """
    Insert jobs into SQLite.

    Existing URLs are ignored so we don't create duplicates.
    """

    connection = sqlite3.connect(DATABASE_FILE)

    inserted = 0
    skipped = 0

    try:
        cursor = connection.cursor()

        for job in jobs:
            cursor.execute(
                """
                INSERT OR IGNORE INTO seen_items (
                    canonical_url,
                    title,
                    company,
                    type,
                    location,
                    remote,
                    posted_date,
                    deadline,
                    source,
                    score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job["canonical_url"],
                    job["title"],
                    job["company"],
                    job["type"],
                    job["location"],
                    job["remote"],
                    job["posted_date"],
                    job["deadline"],
                    job["source"],
                    job["score"],
                ),
            )

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        connection.commit()

    finally:
        connection.close()

    return inserted, skipped


# ---------------------------------------------------------
# Main collector
# ---------------------------------------------------------

def main():
    """Run the OCaml.org collection pipeline."""

    # 1. Load source configuration.
    source = load_ocaml_source()

    # 2. Fetch YAML.
    yaml_data = fetch_jobs(source)

    # 3. Parse YAML.
    data = yaml.safe_load(yaml_data)

    # 4. Get jobs from the top-level "jobs" key.
    raw_jobs = data.get("jobs", [])

    print(f"Found {len(raw_jobs)} jobs")

    # 5. Normalize every job.
    jobs = []

    for raw_job in raw_jobs:
        job = normalize_job(raw_job)
        jobs.append(job)

    # 6. Save to SQLite.
    inserted, skipped = save_jobs(jobs)

    print()
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")


# ---------------------------------------------------------
# Run collector
# ---------------------------------------------------------

if __name__ == "__main__":
    main()