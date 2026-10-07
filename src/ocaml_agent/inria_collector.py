import sqlite3
from pathlib import Path
from urllib.parse import urljoin

from scrapling.fetchers import Fetcher


BASE_URL = "https://jobs.inria.fr"
JOBS_URL = f"{BASE_URL}/public/classic/fr/offres"

DB_PATH = Path("data/agent.db")


def fetch_page(url):
    """Fetch an Inria page using Scrapling Fetcher."""

    response = Fetcher.get(
        url,
        timeout=30,
    )

    print(f"STATUS: {response.status} - {url}")

    if response.status != 200:
        return None

    return response


def discover_offers():
    """Discover current Inria offer URLs."""

    response = fetch_page(JOBS_URL)

    if response is None:
        return []

    offers = []

    for link in response.css("a"):
        title = " ".join(link.text.split())
        href = link.attrib.get("href")

        if not title or not href:
            continue

        if not href.startswith("/public/classic/fr/offres/"):
            continue

        url = urljoin(BASE_URL, href)

        offers.append(
            {
                "title": title,
                "url": url,
            }
        )

    # Remove duplicate URLs while preserving order.
    unique = {}

    for offer in offers:
        unique[offer["url"]] = offer

    offers = list(unique.values())

    print(f"\nDISCOVERED OFFERS: {len(offers)}")

    return offers


def classify_type(title):
    """Classify an Inria opportunity from its title."""

    title_lower = title.lower()

    if "internship" in title_lower or "stage" in title_lower:
        return "intern"

    if "post-doctor" in title_lower or "postdoc" in title_lower:
        return "postdoc"

    if "phd" in title_lower or "doctorant" in title_lower:
        return "phd"

    if "apprenti" in title_lower:
        return "apprenticeship"

    return "full-time"


def is_technical(title):
    """Exclude clearly non-technical administrative roles."""

    title_lower = title.lower()

    excluded_terms = [
        "ressources humaines",
        "human resources",
        "juriste",
        "comptable",
        "comptabilité",
        "administratif",
        "administrative",
        "secrétaire général",
        "secretaire general",
        "maintenance et travaux",
        "business development",
        "contrats de recherche",
        "relations internationales",
        "entrepreneuriat",
        "animation & événementiel",
    ]

    return not any(
        term in title_lower
        for term in excluded_terms
    )


def fetch_offer(offer):
    """Fetch one Inria offer and extract its text."""

    response = fetch_page(offer["url"])

    if response is None:
        return None

    title = response.css("h1::text").get()

    if title:
        title = " ".join(title.split())
    else:
        title = offer["title"]

    text_parts = []

    for element in response.css("main p, main li"):
        text = " ".join(element.text.split())

        if text:
            text_parts.append(text)

    description = "\n".join(text_parts)

    return {
        "title": title,
        "company": "Inria",
        "type": classify_type(title),
        "url": offer["url"],
        "source": "Inria",
        "description": description,
    }


def collect_offers():
    """Discover and fetch all current Inria offers."""

    offers = discover_offers()

    collected = []

    for index, offer in enumerate(offers, start=1):
        print(
            f"[{index}/{len(offers)}] "
            f"{offer['title']}"
        )

        if not is_technical(offer["title"]):
            print("  -> SKIPPED: non-technical")
            continue

        parsed = fetch_offer(offer)

        if parsed:
            collected.append(parsed)

    print(
        f"\nSUCCESSFULLY FETCHED: {len(collected)}"
    )

    return collected


def save_jobs(jobs):
    """Save Inria opportunities into the existing SQLite database."""

    if not jobs:
        print("\nNo Inria opportunities to save.")
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
            print("Skipping opportunity without URL")
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
                None,
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

    print(f"\nDATABASE INSERTED OR ENRICHED: {inserted}")
    print(f"DATABASE SKIPPED: {skipped}")


if __name__ == "__main__":
    jobs = collect_offers()

    print("\n--- PREVIEW ---")

    for job in jobs[:10]:
        print("\nTITLE:", job["title"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
        print("DESCRIPTION LENGTH:", len(job["description"]))
        print(
            "DESCRIPTION PREVIEW:",
            job["description"][:500],
        )

    save_jobs(jobs)
