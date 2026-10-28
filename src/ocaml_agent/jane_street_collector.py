import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from scrapling.fetchers import Fetcher


BASE_URL = "https://www.janestreet.com"

JOBS_URL = f"{BASE_URL}/jobs/main.json"

POSITION_DIRECTORIES_URL = (
    f"{BASE_URL}/static/position-directories.json"
)

DB_PATH = Path("data/agent.db")


TITLE_SIGNALS = (
    r"\bocaml\b",
    r"\boxcaml\b",
    r"\bcompilers?\b",
    r"\bprogramming[- ]languages?\b",
    r"\b(?:programming[- ]language|language) implementation\b",
    r"\btype systems?\b",
    r"\bformal methods?\b",
    r"\bfunctional programming\b",
)

# These phrases identify programming-language work in a job overview. They are
# intentionally more specific than a bare mention of OCaml, which can describe
# a tool used by an otherwise unrelated team.
PROGRAMMING_LANGUAGE_SIGNALS = (
    r"\bcompiler (?:implementation|infrastructure|optimization|optimisation)\b",
    r"\b(?:implementing|building|developing|optimizing|optimising) "
    r"(?:a |the )?compiler\b",
    r"\blanguage implementation\b",
    r"\bprogramming[- ]language (?:research|implementation|development)\b",
    r"\btype systems?\b",
    r"\btype inference\b",
    r"\b(?:design|implement|build|develop|work on)\b[^.]{0,100}"
    r"\b(?:typed )?functional programming\b",
    r"\bpassionate about\b[^.]{0,120}"
    r"\b(?:typed )?functional programming\b",
    r"\blanguage tooling\b",
    r"\bcompiler tooling\b",
    r"\bcompiler infrastructure\b",
)

PROGRAM_VERIFICATION_SIGNALS = (
    r"\bformal methods?\b.*\b(?:program|software|code|language|compiler)\b",
    r"\bformal verification\b.*\b(?:program|software|code|language|compiler)\b",
    r"\bprogram verification\b",
    r"\bverification of (?:programs|software|code)\b",
)

PROGRAM_ANALYSIS_SIGNALS = (
    r"\b(?:static|program) analysis\b.*\b(?:program|software|code|language|compiler)\b",
    r"\b(?:program|software|code|language|compiler)\b.*\b(?:static|program) analysis\b",
)

OCAML_ENGINEERING_SIGNALS = (
    r"\b(?:ocaml|oxcaml)\b(?:\W+\w+){0,4}\W+"
    r"\b(?:software|codebase|libraries?|tooling|tools|systems?)\b",
    r"\b(?:develop|build|implement|maintain|write|engineer)\w*"
    r"(?:[^\w.]+\w+){0,6}[^\w.]+\b(?:ocaml|oxcaml)\b",
)

UNRELATED_TITLE_SIGNALS = (
    r"\b(?:asic|fpga|physical design|hardware)\b",
    r"\bnetwork(?:ing)?\b",
    r"\bwindows\b",
    r"\b(?:financ(?:e|ing)|accounting)\b",
    r"\b(?:cybersecurity|security operations)\b",
    r"\bproduction engineer\b",
    r"\bquantitative trader\b",
    r"\blow[- ]latency\b",
)


def _text_field(job, field):
    """Return a string field, treating malformed values as absent."""

    value = job.get(field)
    return value if isinstance(value, str) else ""


def _matches_any(text, patterns):
    """Return whether text matches one of the case-insensitive patterns."""

    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _has_program_analysis_context(title, overview):
    """Distinguish program analysis from similarly named hardware work."""

    text = f"{title}\n{overview}"
    return _matches_any(text, PROGRAM_ANALYSIS_SIGNALS)


def _has_substantive_overview_relevance(title, overview):
    """Return whether an overview describes substantive relevant work."""

    programming_language_focus = _matches_any(
        overview,
        PROGRAMMING_LANGUAGE_SIGNALS,
    )
    verification_focus = _matches_any(
        overview,
        PROGRAM_VERIFICATION_SIGNALS,
    )
    analysis_focus = _has_program_analysis_context(title, overview)

    if programming_language_focus or verification_focus or analysis_focus:
        return True

    # A generic title can still be relevant when the role itself explicitly
    # describes building or maintaining OCaml/OxCaml software.
    return _matches_any(overview, OCAML_ENGINEERING_SIGNALS)


def _has_programming_language_focus(overview):
    """Return whether an overview goes beyond general OCaml usage."""

    return _matches_any(
        overview,
        PROGRAMMING_LANGUAGE_SIGNALS,
    ) or _matches_any(overview, PROGRAM_VERIFICATION_SIGNALS)


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
    Identify Jane Street roles with direct OCaml or programming-language work.

    Jane Street's active-position payload uses ``position`` for the title and
    ``overview`` for the role description. Metadata such as team and category
    is deliberately ignored: an incidental OCaml mention there does not make a
    role relevant.
    """
    if not isinstance(job, Mapping):
        return False

    title = _text_field(job, "position")
    overview = "\n".join(
        text
        for field in ("overview", "description")
        if (text := _text_field(job, field))
    )

    if _matches_any(title, TITLE_SIGNALS):
        return True

    # "Static analysis" can concern hardware rather than programs, so a title
    # with that phrase needs an overview that makes the programming context
    # explicit.
    if re.search(r"\bstatic analysis\b", title, re.IGNORECASE):
        return _has_program_analysis_context(title, overview)

    if _matches_any(title, UNRELATED_TITLE_SIGNALS):
        # An explicit compiler, programming-language, or program-verification
        # responsibility still wins over a broad job category. A company-wide
        # note that the team uses OCaml does not.
        return _has_programming_language_focus(overview) or (
            _has_program_analysis_context(title, overview)
        )

    return _has_substantive_overview_relevance(title, overview)


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
