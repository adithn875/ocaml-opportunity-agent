import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

BASE_URL = "https://www.frama-c.com"
JOBS_URL = f"{BASE_URL}/html/jobs.html"
DB_PATH = Path("data/agent.db")


def collect_opportunities():
    response = Fetcher.get(JOBS_URL, timeout=30)

    print("STATUS:", response.status)

    if response.status != 200:
        print("Request failed")
        return []

    opportunities = []

    for link in response.css("a.tile"):
        href = link.attrib.get("href", "")

        if not href:
            continue

        url = urljoin(BASE_URL, href)

        job_response = Fetcher.get(url, timeout=30)

        if job_response.status != 200:
            print("FAILED:", url)
            continue

        html = job_response.body.decode(
            "utf-8",
            errors="replace"
        )

        searchable = html.lower()

        if "ocaml" not in searchable:
            continue

        title_elements = link.css("p")
        if not title_elements:
            continue
        title = " ".join(title_elements[0].text.split())

        description = " ".join(
            element.text.strip()
            for element in job_response.css("body p, body li")
            if element.text.strip()
        )

        opportunities.append({
            "title": title,
            "company": "CEA / Frama-C",
            "type": "intern",
            "location": "Paris-Saclay, France",
            "url": url,
            "source": "CEA / Frama-C",
            "description": description,
        })

        print("\nOCAML MATCH:")
        print("TITLE:", title)
        print("URL:", url)

    return opportunities


def save_jobs(jobs):
    if not jobs:
        print("\nNo Frama-C opportunities to save.")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

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
                title = CASE
                    WHEN NULLIF(TRIM(seen_items.title), '') IS NULL
                    THEN excluded.title
                    ELSE seen_items.title
                END,
                description = CASE
                    WHEN NULLIF(TRIM(seen_items.description), '') IS NULL
                    THEN excluded.description
                    ELSE seen_items.description
                END
            WHERE (
                NULLIF(TRIM(seen_items.title), '') IS NULL
                AND NULLIF(TRIM(excluded.title), '') IS NOT NULL
            ) OR (
                NULLIF(TRIM(seen_items.description), '') IS NULL
                AND NULLIF(TRIM(excluded.description), '') IS NOT NULL
            )
            """,
            (
                job["url"],
                job["title"],
                job["company"],
                job["type"],
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

    print(f"\nDATABASE INSERTED OR ENRICHED: {inserted}")
    print(f"DATABASE SKIPPED: {skipped}")


if __name__ == "__main__":
    jobs = collect_opportunities()

    print(f"\nCOLLECTED OPPORTUNITIES: {len(jobs)}")

    save_jobs(jobs)
