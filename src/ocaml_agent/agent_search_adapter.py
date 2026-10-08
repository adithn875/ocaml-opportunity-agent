"""
Agent Search adapter for discovering OCaml opportunities.

This module integrates multiple discovery sources:
- GitHub issues/discussions (public API)
- RSS feeds (OCaml Discuss, HN, others)
- Hacker News posts (direct parsing)

Sources requiring authentication (X/Twitter, LinkedIn) are skipped in cloud.
"""

import json
import re
import sqlite3
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

DB_PATH = Path("data/agent.db")

# OCaml-focused search queries
SEARCH_QUERIES = [
    "OCaml engineer",
    "OCaml developer",
    "OCaml compiler",
    "formal methods",
    "static analysis",
]

# RSS feeds that might contain OCaml job posts
RSS_FEEDS = [
    "https://discuss.ocaml.org/latest.rss",  # OCaml Discuss latest
    "https://hnrss.org/jobs",  # HN jobs
]


def normalize_opportunity(
    source: str,
    title: str,
    company: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    url: Optional[str] = None,
) -> Dict:
    """Normalize a discovery result into database format."""
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip() if company else None,
        "location": (location or "").strip() if location else None,
        "description": (description or "").strip() if description else None,
        "source": source,
        "canonical_url": (url or "").strip() if url else None,
        "type": "job",  # All opportunities are jobs for now
    }


def search_github_issues(query: str) -> List[Dict]:
    """Search GitHub for job-related issues and discussions."""
    results = []
    try:
        # Search GitHub issues with job/hiring keywords
        url = "https://api.github.com/search/issues"
        params = {
            "q": f"{query} type:issue (label:hiring OR label:jobs OR label:opportunity)",
            "per_page": 5,
            "sort": "updated",
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            body = item.get("body", "")
            # Only include if it looks like a job posting
            if any(kw in (item.get("title", "") + body).lower() for kw in ["job", "hiring", "position", "role", "engineer"]):
                result = normalize_opportunity(
                    source="agent-search:github",
                    title=item.get("title", ""),
                    company=None,
                    location=None,
                    description=body[:400] if body else None,
                    url=item.get("html_url"),
                )
                if result["title"]:
                    results.append(result)

    except Exception as e:
        print(f"GitHub search error: {e}")

    return results


def search_github_discussions(query: str) -> List[Dict]:
    """Search GitHub discussions for opportunities."""
    results = []
    try:
        # Use GitHub GraphQL to search discussions (more reliable for jobs)
        url = "https://api.github.com/graphql"

        query_text = f'"{query}" category:jobs'

        gql = {
            "query": f"""
            query {{
              search(query: "{query_text}", type: DISCUSSION, first: 5) {{
                nodes {{
                  ... on Discussion {{
                    title
                    body
                    url
                    updatedAt
                  }}
                }}
              }}
            }}
            """
        }

        resp = requests.post(url, json=gql, timeout=10, headers={
            "User-Agent": "curl/8.7.1"
        })

        if resp.status_code == 200:
            data = resp.json()
            for node in data.get("data", {}).get("search", {}).get("nodes", []):
                if node:
                    result = normalize_opportunity(
                        source="agent-search:github",
                        title=node.get("title", ""),
                        description=node.get("body", "")[:400],
                        url=node.get("url"),
                    )
                    if result["title"]:
                        results.append(result)

    except Exception as e:
        print(f"GitHub discussions error: {e}")

    return results


def fetch_rss_feed(feed_url: str, source_name: str = "rss") -> List[Dict]:
    """Fetch and parse RSS feed for job opportunities."""
    results = []
    try:
        import feedparser

        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:30]:  # Check more entries
            title = entry.get("title", "")
            content = entry.get("summary", "") or entry.get("description", "")

            # Look for job-related keywords
            full_text = (title + " " + content).lower()
            if any(kw in full_text for kw in ["job", "hiring", "position", "role", "engineer", "internship", "research"]):
                result = normalize_opportunity(
                    source=f"agent-search:{source_name}",
                    title=title,
                    description=content[:400] if content else None,
                    url=entry.get("link"),
                )
                if result["title"]:
                    results.append(result)

    except Exception as e:
        print(f"RSS feed error for {feed_url}: {e}")

    return results


def search_hn_jobs_api() -> List[Dict]:
    """Search Hacker News job posts via Algolia API."""
    results = []
    try:
        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": "OCaml",
            "tags": "story,job",
            "hitsPerPage": 10,
        }

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get("hits", []):
            title = hit.get("title", "")
            # Filter to job-related posts
            if any(kw in title.lower() for kw in ["hiring", "job", "position", "looking"]):
                result = normalize_opportunity(
                    source="agent-search:hn",
                    title=title,
                    description=None,
                    url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                )
                if result["title"]:
                    results.append(result)

    except Exception as e:
        print(f"HN jobs API error: {e}")

    return results


def deduplicate_opportunities(opportunities: List[Dict]) -> List[Dict]:
    """
    Deduplicate opportunities based on title/URL.

    Returns list of deduplicated opportunities.
    """
    seen_urls = set()
    seen_titles = set()
    unique = []

    for opp in opportunities:
        url = opp.get("canonical_url", "")
        title = (opp.get("title", "") or "").lower().strip()

        # Skip if we've seen this URL
        if url and url in seen_urls:
            continue
        if title and title in seen_titles:
            continue

        unique.append(opp)
        if url:
            seen_urls.add(url)
        if title:
            seen_titles.add(title)

    return unique


def insert_opportunities(connection, opportunities: List[Dict]) -> int:
    """Insert opportunities into database, skipping duplicates. Returns count inserted."""
    count = 0
    cursor = connection.cursor()

    for opp in opportunities:
        try:
            # Check if URL already exists
            if opp.get("canonical_url"):
                cursor.execute(
                    "SELECT id FROM seen_items WHERE canonical_url = ?",
                    (opp["canonical_url"],),
                )
                if cursor.fetchone():
                    continue

            # Insert
            cursor.execute(
                """
                INSERT INTO seen_items
                (title, company, location, description, source, canonical_url, type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opp.get("title"),
                    opp.get("company"),
                    opp.get("location"),
                    opp.get("description"),
                    opp.get("source"),
                    opp.get("canonical_url"),
                    opp.get("type", "job"),
                ),
            )
            count += 1

        except Exception as e:
            print(f"Error inserting opportunity: {e}")

    return count


def main():
    """Run agent-search discovery and insert results."""
    print("\n" + "=" * 60)
    print("AGENT SEARCH DISCOVERY")
    print("=" * 60)

    all_opportunities = []

    # Search GitHub for each query
    print("\nSearching GitHub issues...")
    for query in SEARCH_QUERIES:
        try:
            results = search_github_issues(query)
            all_opportunities.extend(results)
            print(f"  {query}: {len(results)} results")
        except Exception as e:
            print(f"  {query}: error - {e}")
        time.sleep(0.3)

    # Fetch RSS feeds
    print("\nFetching RSS feeds...")
    for feed_url in RSS_FEEDS:
        source_name = "ocaml-discuss" if "discuss.ocaml.org" in feed_url else "hn" if "hnrss" in feed_url else "rss"
        try:
            results = fetch_rss_feed(feed_url, source_name)
            all_opportunities.extend(results)
            print(f"  {feed_url[:40]}: {len(results)} results")
        except Exception as e:
            print(f"  {feed_url[:40]}: error - {e}")

    # Search HN jobs API
    print("\nSearching Hacker News jobs...")
    try:
        results = search_hn_jobs_api()
        all_opportunities.extend(results)
        print(f"  Found {len(results)} results")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\nTotal opportunities discovered: {len(all_opportunities)}")

    # Deduplicate
    deduped = deduplicate_opportunities(all_opportunities)
    print(f"After deduplication: {len(deduped)}")

    # Insert into database
    try:
        connection = sqlite3.connect(DB_PATH)
        inserted = insert_opportunities(connection, deduped)
        connection.commit()
        connection.close()
        print(f"Successfully inserted {inserted} new opportunities")
    except Exception as e:
        print(f"Database error: {e}")
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

