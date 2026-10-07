import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher


BASE_URL = "https://ocamlpro.com"

JOBS_URL = f"{BASE_URL}/jobs/"
INTERNSHIPS_URL = f"{BASE_URL}/internships/"

DB_PATH = Path("data/agent.db")


def fetch_page(url):
    """Fetch an OCamlPro page using Scrapling Fetcher."""

    response = Fetcher.get(
        url,
        timeout=30,
    )

    print(f"STATUS: {response.status} - {url}")

    if response.status != 200:
        print("Request failed")
        return None

    return response


def collect_job():
    """Collect current OCamlPro job listings."""

    response = fetch_page(JOBS_URL)

    if response is None:
        return []

    jobs = []

    for link in response.css("a"):
        text = " ".join(link.text.split())
        href = link.attrib.get("href")

        if not text or not href:
            continue

        if text.lower() != "senior r&d engineer":
            continue

        url = urljoin(BASE_URL, href)

        jobs.append(
            {
                "title": text,
                "company": "OCamlPro",
                "type": "full-time",
                "location": "Paris, France",
                "url": url,
                "source": "OCamlPro",
            }
        )

    return jobs


def collect_internships():
    """
    Collect only current internships.

    Current internships appear before the
    'Past internships' heading.

    Everything after that heading is ignored.
    """

    response = fetch_page(INTERNSHIPS_URL)

    if response is None:
        return []

    internships = []

    # Find the two section headings.
    headings = response.css("h2.page-subtitle")

    current_heading = None
    past_heading = None

    for heading in headings:
        text = " ".join(
            heading.text.split()
        ).lower()

        if text == "looking for an internship?":
            current_heading = heading

        elif text == "past internships":
            past_heading = heading

    if current_heading is None:
        print(
            "WARNING: Current internship section "
            "was not found."
        )
        return []

    if past_heading is None:
        print(
            "WARNING: Past internship section "
            "was not found."
        )
        return []

    # The verified HTML structure is:
    #
    # h2 Looking for an internship?
    # <br>
    # <div class="row ...">
    #     current cards
    # </div>
    #
    # <hr>
    #
    # h2 Past internships
    # <br>
    # <div class="row ...">
    #     old cards
    # </div>
    #
    # We locate the first row after the current heading.
    # That row contains only current internships.

    rows = response.css(
        "div.row.row-cols-auto.gy-4"
    )

    if not rows:
        print(
            "WARNING: Internship card rows "
            "were not found."
        )
        return []

    # According to the verified page structure:
    #
    # rows[0] = current internships
    # rows[1] = past internships
    #
    # We only use rows[0].
    current_row = rows[0]

    for card in current_row.css("div.card"):
        title_element = card.css(
            ".card-header"
        )

        if not title_element:
            continue

        title = " ".join(
            title_element[0].text.split()
        )

        link_element = card.css(
            ".card-title a"
        )

        if not link_element:
            continue

        link = link_element[0]

        href = link.attrib.get("href")

        if not href:
            continue

        url = urljoin(
            BASE_URL,
            href,
        )

        description_element = card.css(
            ".card-text"
        )

        description = ""

        if description_element:
            description = " ".join(
                description_element[0].text.split()
            )

        level_text = " ".join(
            link.text.split()
        )

        internships.append(
            {
                "title": title,
                "company": "OCamlPro",
                "type": "intern",
                "location": "Paris, France",
                "url": url,
                "source": "OCamlPro",
                "description": description,
                "level": level_text,
            }
        )

    return internships


def collect_all():
    """Collect current OCamlPro jobs and internships."""

    jobs = collect_job()
    internships = collect_internships()

    collected = jobs + internships

    print(
        f"\nCURRENT JOBS: {len(jobs)}"
    )

    print(
        f"CURRENT INTERNSHIPS: {len(internships)}"
    )

    print(
        f"TOTAL COLLECTED: {len(collected)}"
    )

    return collected


def save_jobs(jobs):
    """Save OCamlPro opportunities into SQLite."""

    if not jobs:
        print(
            "\nNo OCamlPro opportunities to save."
        )
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
            print(
                "Skipping opportunity without URL"
            )
            continue

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
                canonical_url,
                job.get("title"),
                job.get("company"),
                job.get("type"),
                job.get("location"),
                job.get("source"),
                job.get("description"),
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
    jobs = collect_all()

    print(
        "\n--- COLLECTED OPPORTUNITIES ---"
    )

    for job in jobs:
        print(
            f"\nTITLE: {job['title']}"
        )
        print(
            f"TYPE: {job['type']}"
        )
        print(
            f"LOCATION: {job['location']}"
        )
        print(
            f"URL: {job['url']}"
        )

    save_jobs(jobs)
