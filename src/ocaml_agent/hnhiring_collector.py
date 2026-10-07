"""
OCaml Opportunity Agent - HNHIRING Collector

Milestone 2:
Collect OCaml-related opportunities from HNHIRING.

Scrapling is used for fetching.
The raw HTML response body is parsed directly.

If the current month has zero OCaml jobs, the collector
reports that cleanly and does not scrape an older month.
"""

from pathlib import Path
import re
from html import unescape

import yaml
from scrapling.fetchers import Fetcher


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

SOURCES_FILE = ROOT / "config" / "sources.yaml"


# ---------------------------------------------------------
# Load source configuration
# ---------------------------------------------------------

def load_hnhiring_source():
    """Find the HNHIRING OCaml source by its exact URL."""

    with open(SOURCES_FILE, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    target_url = "https://hnhiring.com/technologies/ocaml"

    for source in config.get("aggregators", []):

        source_url = source.get("url", "").rstrip("/")

        if source_url == target_url:
            return source

    raise ValueError(
        f"HNHIRING source not found: {target_url}"
    )


# ---------------------------------------------------------
# Fetch page
# ---------------------------------------------------------

def fetch_page(source):
    """Fetch the HNHIRING OCaml page using Scrapling."""

    url = source["url"]

    print(f"Fetching: {url}")

    response = Fetcher.get(
        url,
        timeout=30,
    )

    print(f"HTTP status: {response.status}")

    if response.status != 200:
        raise RuntimeError(
            f"Failed to fetch HNHIRING: HTTP {response.status}"
        )

    if not response.body:
        raise RuntimeError(
            "HNHIRING returned an empty response body"
        )

    print(
        f"Response body: {len(response.body)} bytes"
    )

    return response.body


# ---------------------------------------------------------
# Parse page
# ---------------------------------------------------------

def parse_jobs(html_data):
    """
    Parse the current HNHIRING OCaml page.

    Returns:
        jobs: list of jobs
        period: month/year shown by HNHIRING
        job_count: number reported by HNHIRING
    """

    html = html_data.decode(
        "utf-8",
        errors="replace",
    )

    # -----------------------------------------------------
    # Detect period
    # -----------------------------------------------------

    period_match = re.search(
        r"Ocaml Jobs\s*-\s*([A-Za-z]+\s+\d{4})",
        html,
        re.IGNORECASE,
    )

    period = None

    if period_match:
        period = period_match.group(1)

        print(
            f"Detected HNHIRING period: {period}"
        )

    # -----------------------------------------------------
    # Detect job count
    # -----------------------------------------------------

    count_match = re.search(
        r'class="center page-subtitle">\s*'
        r"(\d+)\s+jobs?\s+found",
        html,
        re.IGNORECASE,
    )

    if not count_match:
        raise RuntimeError(
            "Could not determine HNHIRING job count"
        )

    job_count = int(count_match.group(1))

    print(
        f"HNHIRING reports: "
        f"{job_count} jobs found"
    )

    # -----------------------------------------------------
    # Current month has no jobs
    # -----------------------------------------------------

    if job_count == 0:
        return [], period, 0

    # -----------------------------------------------------
    # Extract jobs
    # -----------------------------------------------------

    jobs = []

    # HNHIRING stores current jobs inside:
    #
    # <ul class="jobs">
    #
    # If jobs exist, inspect the list items.
    jobs_section_match = re.search(
        r'<ul class="jobs">(.*?)</ul>',
        html,
        re.IGNORECASE | re.DOTALL,
    )

    if not jobs_section_match:
        raise RuntimeError(
            "HNHIRING reported jobs but no jobs section "
            "was found"
        )

    jobs_html = jobs_section_match.group(1)

    # Extract links from the jobs section.
    link_matches = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',
        jobs_html,
        re.IGNORECASE | re.DOTALL,
    )

    for href, content in link_matches:

        href = unescape(href)

        # Remove HTML tags from link text.
        title = re.sub(
            r"<[^>]+>",
            " ",
            content,
        )

        title = unescape(title)

        # Normalize whitespace.
        title = " ".join(title.split())

        if not title:
            continue

        jobs.append(
            {
                "title": title,
                "url": href,
            }
        )

    return jobs, period, job_count


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():
    """Run the HNHIRING collector."""

    # 1. Load source.
    source = load_hnhiring_source()

    # 2. Fetch page.
    html_data = fetch_page(source)

    # 3. Parse page.
    jobs, period, job_count = parse_jobs(html_data)

    print()

    if job_count == 0:

        print(
            f"No OCaml jobs currently listed "
            f"for {period}."
        )

        print(
            "Older months were not scraped."
        )

        return

    print(
        f"Found {len(jobs)} candidate jobs"
    )

    # 4. Display jobs.
    for job in jobs:

        print("-" * 60)

        print(f"Title: {job['title']}")
        print(f"URL: {job['url']}")


# ---------------------------------------------------------
# Run collector
# ---------------------------------------------------------

if __name__ == "__main__":
    main()