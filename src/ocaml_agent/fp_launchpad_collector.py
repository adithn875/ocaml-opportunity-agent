
"""Collect relevant opportunities and events from FP Launchpad."""

import re
import sqlite3
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

from scrapling.fetchers import Fetcher


BASE_URL = "https://fplaunchpad.org"
UPDATES_URL = f"{BASE_URL}/updates/"
DB_PATH = Path("data/agent.db")

# Only retain categories that may contain a real opportunity or event.
ALLOWED_CATEGORIES = {
    "announcement",
    "event",
    "talk",
    "seminar",
    "workshop",
    "conference",
}

# Require a meaningful opportunity signal for announcements.
OPPORTUNITY_TERMS = (
    "application",
    "apply",
    "fellowship",
    "internship",
    "intern",
    "hiring",
    "job opening",
    "summer school",
    "winter school",
    "scholarship",
    "grant",
    "call for proposals",
    "call for papers",
    "registration",
    "hackathon",
)

# These posts are usually reading roundups rather than opportunities.
EXCLUDED_TITLE_TERMS = (
    "fpl reading:",
)


def clean_text(value):
    """Normalize whitespace in extracted text."""
    return " ".join((value or "").split())


def normalize_url(url):
    """Normalize a URL for consistent database deduplication."""
    url = urldefrag(url)[0]
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()

    if host not in {"fplaunchpad.org", "www.fplaunchpad.org"}:
        return None

    # Remove tracking parameters without removing meaningful query data.
    query_parts = [
        part
        for part in parsed.query.split("&")
        if part
        and not part.lower().startswith(
            ("utm_", "fbclid=", "gclid=")
        )
    ]

    return parsed._replace(
        scheme="https",
        netloc="fplaunchpad.org",
        query="&".join(query_parts),
        fragment="",
    ).geturl()


def fetch_updates():
    """Fetch the Updates page, failing clearly on network/HTTP errors."""
    response = Fetcher.get(UPDATES_URL, timeout=30)
    status = getattr(response, "status", None)

    print(f"FP Launchpad HTTP status: {status}")

    if status != 200:
        raise RuntimeError(
            f"FP Launchpad Updates returned HTTP {status}"
        )

    return response


def extract_category(entry_text):
    """Find a known content category in an entry's visible text."""
    lines = [
        clean_text(line).lower()
        for line in entry_text.splitlines()
        if clean_text(line)
    ]

    for line in lines:
        if line in ALLOWED_CATEGORIES:
            return line

    return None


def extract_date(entry_text):
    """Extract a visible date when its format is recognizable."""
    patterns = (
        # 24 Sep 2026, 24 September 2026, 6 Mar 2026
        r"\b\d{1,2}\s+"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{4}\b",
        # 2026-09-24
        r"\b\d{4}-\d{2}-\d{2}\b",
    )

    for pattern in patterns:
        match = re.search(pattern, entry_text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


def is_relevant(title, category, entry_text):
    """Filter out general posts and routine reading roundups."""
    normalized_title = title.lower()

    if any(term in normalized_title for term in EXCLUDED_TITLE_TERMS):
        return False

    if category in {"event", "talk", "seminar", "workshop", "conference"}:
        return True

    searchable = f"{title} {entry_text}".lower()

    if category == "announcement":
        return any(term in searchable for term in OPPORTUNITY_TERMS)

    return False


def collect_opportunities():
    """
    Collect relevant entries from the Updates page.

    Uses visible links and their surrounding list/article/card context.
    If the page structure no longer exposes identifiable entries, fail
    visibly rather than reporting a misleading successful empty result.
    """
    response = fetch_updates()
    opportunities = []
    seen_urls = set()
    inspected_links = 0

    for link in response.css("a"):
        title = clean_text(link.text)
        href = link.attrib.get("href")

        if not title or not href:
            continue

        url = normalize_url(urljoin(UPDATES_URL, href))

        if not url:
            continue

        # The updates page itself is not an opportunity.
        if url.rstrip("/") == UPDATES_URL.rstrip("/"):
            continue

               # Avoid processing the same URL multiple times on one page.
        if url in seen_urls:
            continue

        inspected_links += 1

        # Handle the announcement bar separately below.
        if "announcement-bar" not in link.attrib.get("class", ""):
            seen_urls.add(url)

               # Use the site's actual update-item container.
        containers = link.xpath(
            "ancestor::li[contains(@class, 'update-item')][1]"
        )

        if not containers:
            continue

        container = containers[0]
        entry_text = clean_text(container.text)
        title_links = container.css("h3.update-title a")

        if not title_links or title != clean_text(title_links[0].text):
            continue

        # FP Launchpad stores the category in the data-type attribute.
        category_map = {
            "news": "announcement",
            "event": "event",
            "talk": "talk",
            "seminar": "seminar",
        }

        category = category_map.get(
            container.attrib.get("data-type", "").lower()
        )

        if category not in ALLOWED_CATEGORIES:
            continue

        if not is_relevant(title, category, entry_text):
            continue

        description = entry_text
        posted_date = extract_date(entry_text)

        opportunities.append(
            {
                "title": title,
                "company": "FP Launchpad",
                "type": (
                    "event"
                    if category in {
                        "event",
                        "talk",
                        "seminar",
                        "workshop",
                        "conference",
                    }
                    else "research"
                ),
                "location": None,
                "remote": None,
                "posted_date": posted_date,
                "deadline": None,
                "url": url,
                "source": "FP Launchpad",
                "description": description,
            }
        )

    # The current fellowship announcement is outside the update-item list.
    for banner in response.css("a.announcement-bar"):
        title = clean_text(banner.text)
        href = banner.attrib.get("href")

        if not title or not href:
            continue

        url = normalize_url(urljoin(UPDATES_URL, href))

        if not url or url in seen_urls:
            continue

        if is_relevant(title, "announcement", title):
            seen_urls.add(url)
            opportunities.append(
                {
                    "title": title,
                    "company": "FP Launchpad",
                    "type": "research",
                    "location": None,
                    "remote": None,
                    "posted_date": None,
                    "deadline": None,
                    "url": url,
                    "source": "FP Launchpad",
                    "description": title,
                }
            )

    print(f"FP Launchpad links inspected: {inspected_links}")
    print(f"FP Launchpad relevant entries: {len(opportunities)}")

    if inspected_links == 0:
        raise RuntimeError(
            "No FP Launchpad links were found; inspect the page structure."
        )

    return opportunities


def save_opportunities(opportunities):
    """Save entries without overwriting existing scores or notification state."""
    inserted = 0
    skipped = 0

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as con:
        # Ensure the existing schema is initialized.
        from .db import SCHEMA
        con.executescript(SCHEMA)

        for item in opportunities:
            url = item.get("url")
            title = item.get("title")

            if not url or not title:
                skipped += 1
                continue

            cursor = con.execute(
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
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_url) DO UPDATE SET
                    description = CASE
                        WHEN NULLIF(TRIM(excluded.description), '') IS NOT NULL
                         AND (
                            NULLIF(TRIM(seen_items.description), '') IS NULL
                            OR LENGTH(excluded.description) >
                               LENGTH(seen_items.description)
                         )
                        THEN excluded.description
                        ELSE seen_items.description
                    END
                """,
                (
                    url,
                    title,
                    item.get("company"),
                    item.get("type"),
                    item.get("location"),
                    item.get("remote"),
                    item.get("posted_date"),
                    item.get("deadline"),
                    item.get("source"),
                    item.get("description"),
                ),
            )

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

    print(f"FP Launchpad inserted or enriched: {inserted}")
    print(f"FP Launchpad unchanged or skipped: {skipped}")


def main():
    opportunities = collect_opportunities()
    save_opportunities(opportunities)


if __name__ == "__main__":
    main()
