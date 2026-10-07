import json
import sqlite3
from pathlib import Path

from scrapling.fetchers import Fetcher


BASE_URL = "https://www.janestreet.com"

JOBS_URL = f"{BASE_URL}/jobs/main.json"

POSITION_DIRECTORIES_URL = (
    f"{BASE_URL}/static/position-directories.json"
)

DB_PATH = Path("data/agent.db")


def fetch_json(url):
    """Fetch and decode a JSON endpoint using Scrapling."""
    response = Fetcher.get(url, timeout=30)

    if response.status != 200:
        print(f"Request failed: {response.status} - {url}")
        return None

    return json.loads(response.body.decode("utf-8"))


def discover_jobs():
    """Discover all currently active Jane Street jobs."""
    print("Fetching Jane Street job data...")

    jobs = fetch_json(JOBS_URL)
    position_directories = fetch_json(
        POSITION_DIRECTORIES_URL
    )

    if jobs is None or position_directories is None:
        return []

    position_ids = {
        str(position_id)
        for position_id in position_directories
    }

    active_jobs = [
        job
        for job in jobs
        if str(job.get("id")) in position_ids
    ]

    print(f"ALL JOB RECORDS: {len(jobs)}")
    print(f"ACTIVE JOB RECORDS: {len(active_jobs)}")

    return active_jobs


def is_ocaml_job(job):
    """
    Find jobs that mention OCaml somewhere in the Jane Street
    job record.

    This intentionally acts as a broad candidate filter.
    Milestone 3 can perform more precise relevance scoring.
    """
    searchable_text = json.dumps(job).lower()

    return "ocaml" in searchable_text


def fetch_position(url):
    """Fetch and parse an individual Jane Street position page."""
    response = Fetcher.get(url, timeout=30)

    if response.status != 200:
        print(
            f"Position request failed: "
            f"{response.status} - {url}"
        )
        return None

    # Job title
    title = " ".join(
        x.text.strip()
        for x in response.css("h4.page-heading")
    )

    # Subheading information
    names = [
        x.text.strip()
        for x in response.css(".subheading .name")
    ]

    # Location
    location = response.css(
        ".subheading .name.city::text"
    ).get()

    # Job description
    description = " ".join(
        x.text.strip()
        for x in response.css(
            ".job-content p, .job-content li"
        )
    )

    # Apply URL
    apply_url = response.css(
        "a.apply-button::attr(href)"
    ).get()

    if apply_url and apply_url.startswith("/"):
        apply_url = BASE_URL + apply_url

    return {
        "id": url.rstrip("/").split("/")[-1],
        "title": title,
        "company": "Jane Street",
        "location": (
            location.strip()
            if location
            else None
        ),
        "department": (
            names[1]
            if len(names) > 1
            else None
        ),
        "team": (
            names[2]
            if len(names) > 2
            else None
        ),
        "description": description,
        "url": url,
        "apply_url": apply_url,
        "source": "Jane Street",
    }


def collect_ocaml_jobs():
    """Discover, filter, and parse OCaml-related Jane Street jobs."""
    active_jobs = discover_jobs()

    ocaml_jobs = [
        job
        for job in active_jobs
        if is_ocaml_job(job)
    ]

    print(
        f"OCAML CANDIDATES: {len(ocaml_jobs)}"
    )

    collected = []

    for index, job in enumerate(
        ocaml_jobs,
        start=1,
    ):
        job_id = job.get("id")

        position_url = (
            f"{BASE_URL}/"
            f"join-jane-street/"
            f"position/{job_id}/"
        )

        print(
            f"[{index}/{len(ocaml_jobs)}] "
            f"Fetching {job.get('position')} "
            f"({job_id})"
        )

        parsed = fetch_position(position_url)

        if parsed:
            collected.append(parsed)

    return collected


def save_jobs(jobs):
    """
    Save collected jobs into the existing SQLite database.

    canonical_url is the Jane Street position URL. Existing
    records retain their metadata while missing descriptions are
    filled from the current source page.
    """
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = sqlite3.connect(DB_PATH)

    inserted = 0
    skipped = 0

    for job in jobs:
        cursor = con.execute(
            """
            INSERT INTO seen_items (
                canonical_url,
                title,
                company,
                type,
                location,
                source,
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_url) DO UPDATE SET
                description = excluded.description
            WHERE NULLIF(TRIM(excluded.description), '') IS NOT NULL
              AND NULLIF(TRIM(seen_items.description), '') IS NULL
            """,
            (
                job["url"],
                job["title"],
                job["company"],
                None,
                job["location"],
                job["source"],
                job["description"],
            ),
        )

        if cursor.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    con.commit()
    con.close()

    print(
        f"\nDATABASE INSERTED OR ENRICHED: {inserted}"
    )

    print(
        f"DATABASE SKIPPED: {skipped}"
    )


if __name__ == "__main__":
    jobs = collect_ocaml_jobs()

    print(
        f"\nCOLLECTED JOBS: {len(jobs)}"
    )

    save_jobs(jobs)
