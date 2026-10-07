import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher

BASE_URL = "https://www.trust-in-soft.com"
CAREERS_URL = f"{BASE_URL}/careers"
DB_PATH = Path("data/agent.db")


def collect_opportunities():
    response = Fetcher.get(CAREERS_URL, timeout=30)

    print("STATUS:", response.status)

    if response.status != 200:
        print("Request failed")
        return []

    opportunities = []

    for link in response.css("a"):
        text = " ".join(link.text.split())
        href = link.attrib.get("href", "")

        if not text or "read more" not in text.lower():
            continue

        url = urljoin(BASE_URL, href)

        job_response = Fetcher.get(url, timeout=30)

        if job_response.status != 200:
            print("FAILED:", url)
            continue

        # TrustInSoft exposes the job description in the raw HTML.
        html = job_response.body.decode(
            "utf-8",
            errors="replace"
        )

        searchable = (
            text + " " + html
        ).lower()

        print("\nCHECKING:", url)
        print("OCAML:", "ocaml" in searchable)

        if "ocaml" not in searchable:
            continue

        title = text

        h1 = job_response.css("h1")

        if h1:
            title = " ".join(h1[0].text.split())

        opportunities.append({
            "title": title,
            "company": "TrustInSoft",
            "description": " ".join(x.text.split() for x in job_response.css("main p, main li") if x.text.strip()),
            "type": "full-time",
            "location": None,
            "url": url,
            "source": "TrustInSoft",
        })

        print("OCAML MATCH:", title)

    return opportunities


def save_jobs(jobs):
    if not jobs:
        print("\nNo TrustInSoft opportunities to save.")
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
                description = excluded.description
            WHERE NULLIF(TRIM(excluded.description), '') IS NOT NULL
              AND NULLIF(TRIM(seen_items.description), '') IS NULL
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
