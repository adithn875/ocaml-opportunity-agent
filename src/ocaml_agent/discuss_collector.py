"""
OCaml Opportunity Agent - OCaml Discuss Collector

Milestone 2:
Collect jobs from the OCaml Discuss Jobs RSS feed
and store them in SQLite.

Scrapling is used for fetching.
Python's XML parser is used for parsing RSS.
SQLite is used for storage.
"""

from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET
from html import unescape

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

def load_discuss_source():
    """Find the OCaml Discuss Jobs source in sources.yaml."""

    with open(SOURCES_FILE, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    for source in config.get("aggregators", []):
        if source.get("name") == "OCaml Discuss Jobs":
            return source

    raise ValueError(
        "OCaml Discuss Jobs source was not found in sources.yaml"
    )


# ---------------------------------------------------------
# Fetch RSS feed
# ---------------------------------------------------------

def fetch_feed(source):
    """Download the OCaml Discuss RSS feed using Scrapling."""

    url = source["url"].rstrip("/") + ".rss"

    print(f"Fetching: {url}")

    response = Fetcher.get(
        url,
        timeout=30,
    )

    if response.status != 200:
        raise RuntimeError(
            f"Failed to fetch RSS feed: HTTP {response.status}"
        )

    return response.body


# ---------------------------------------------------------
# Clean URL
# ---------------------------------------------------------

def clean_url(url):
    """Decode HTML entities and remove unwanted trailing characters."""

    if not url:
        return None

    # Convert things like &amp; back to &.
    url = unescape(url)

    # Remove whitespace.
    url = url.strip()

    # Remove punctuation that can accidentally be captured
    # from HTML/text surrounding the URL.
    url = url.rstrip(".,;:!?)]}")

    return url


# ---------------------------------------------------------
# Extract job URL
# ---------------------------------------------------------

def extract_job_url(description):
    """
    Find the most likely external job URL from a Discuss post.

    Returns None when there is no clearly identifiable
    job/career URL.
    """

    if not description:
        return None

    # Find URLs inside the HTML description.
    pattern = r"https?://[^\"\s<>]+"

    urls = re.findall(pattern, description)

    # Clean URLs.
    urls = [
        clean_url(url)
        for url in urls
    ]

    # Remove empty URLs.
    urls = [
        url
        for url in urls
        if url
    ]

    # Remove duplicates while keeping original order.
    urls = list(dict.fromkeys(urls))

    # Remove OCaml Discuss URLs.
    urls = [
        url
        for url in urls
        if "discuss.ocaml.org" not in url.lower()
    ]

    # Remove obvious image URLs.
    image_extensions = (
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".webp",
    )

    urls = [
        url
        for url in urls
        if not url.lower().split("?")[0].endswith(image_extensions)
    ]

    # Prefer URLs that look like actual job/career pages.
    job_keywords = (
        "/careers",
        "/career",
        "/jobs",
        "/job/",
        "/positions",
        "/position",
        "/openings",
        "/vacancies",
        "/opportunities",
        "job=",
        "jobs=",
        "careers=",
    )

    for url in urls:
        url_lower = url.lower()

        if any(keyword in url_lower for keyword in job_keywords):
            return url

    # Don't guess if there is no obvious job URL.
    return None


# ---------------------------------------------------------
# Parse RSS
# ---------------------------------------------------------

def parse_items(rss_data):
    """Parse RSS XML and return the job items."""

    root = ET.fromstring(rss_data)

    jobs = []

    for item in root.findall("./channel/item"):

        title = item.findtext("title")
        description = item.findtext("description")
        topic_url = item.findtext("link")
        published = item.findtext("pubDate")

        # Clean basic fields.
        if title:
            title = unescape(title).strip()

        if topic_url:
            topic_url = clean_url(topic_url)

        if published:
            published = published.strip()

        # Try to find the actual external job/application URL.
        job_url = extract_job_url(description)

        # Skip malformed RSS items.
        if not title or not topic_url:
            continue

        jobs.append(
            {
                "title": title,
                "description": description,
                "topic_url": topic_url,
                "published": published,
                "job_url": job_url,
            }
        )

    return jobs


# ---------------------------------------------------------
# Choose canonical URL
# ---------------------------------------------------------

def get_canonical_url(job):
    """
    Use the external job URL when available.

    Otherwise use the OCaml Discuss topic URL.
    """

    if job["job_url"]:
        return job["job_url"]

    return job["topic_url"]


# ---------------------------------------------------------
# Save jobs to SQLite
# ---------------------------------------------------------

def save_jobs(jobs):
    """Insert Discuss jobs into the existing SQLite database."""

    connection = sqlite3.connect(DATABASE_FILE)

    inserted = 0
    skipped = 0

    try:
        cursor = connection.cursor()

        for job in jobs:

            canonical_url = get_canonical_url(job)

            # A valid canonical URL is required by the database.
            if not canonical_url:
                continue

            cursor.execute(
                """
                INSERT INTO seen_items (
                    canonical_url,
                    title,
                    company,
                    type,
                    location,
                    remote,
                    posted_date,
                    deadline,
                    source,
                    score,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    description = excluded.description
                WHERE NULLIF(TRIM(excluded.description), '') IS NOT NULL
                  AND NULLIF(TRIM(seen_items.description), '') IS NULL
                """,
                (
                    canonical_url,
                    job["title"],
                    None,
                    None,
                    None,
                    None,
                    job["published"],
                    None,
                    "OCaml Discuss Jobs",
                    None,
                    job["description"],
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
# Main
# ---------------------------------------------------------

def main():
    """Run the OCaml Discuss collector."""

    # 1. Load source configuration.
    source = load_discuss_source()

    # 2. Fetch RSS using Scrapling.
    rss_data = fetch_feed(source)

    # 3. Parse RSS.
    jobs = parse_items(rss_data)

    print(f"\nFound {len(jobs)} RSS items")

    # 4. Save jobs into SQLite.
    inserted, skipped = save_jobs(jobs)

    print()
    print(f"Inserted: {inserted}")
    print(f"Skipped:  {skipped}")


# ---------------------------------------------------------
# Run collector
# ---------------------------------------------------------

if __name__ == "__main__":
    main()
