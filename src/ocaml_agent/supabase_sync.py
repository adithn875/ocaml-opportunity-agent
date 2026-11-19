"""Upload the locally collected jobs to Supabase's PostgREST API."""
import argparse
import json
import os
from pathlib import Path
from urllib import error, request

from . import db


DB_PATH = Path("data/agent.db")


def load_jobs(database_path: Path | str = DB_PATH) -> list[dict]:
    """Return SQLite jobs in the format expected by the Supabase jobs table."""
    with db.connect(database_path) as connection:
        connection.row_factory = None
        rows = connection.execute(
            """
            SELECT
                canonical_url,
                title,
                company,
                type,
                location,
                remote,
                posted_date,
                deadline,
                source,
                description,
                score,
                llm_score,
                final_score,
                first_seen
            FROM seen_items
            ORDER BY id
            """
        ).fetchall()

    fields = (
        "source_url",
        "title",
        "company",
        "employment_type",
        "location",
        "remote",
        "posted_date",
        "deadline",
        "source",
        "description",
        "deterministic_score",
        "llm_score",
        "final_score",
        "first_seen",
    )
    return [dict(zip(fields, row)) for row in rows]


def load_source_runs(database_path: Path | str = DB_PATH) -> list[dict]:
    """Return collector health records in the format expected by Supabase."""
    with db.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, source, started_at, finished_at, duration_seconds,
                   status, new_items, error
            FROM source_runs
            ORDER BY id
            """
        ).fetchall()

    return [
        {
            "source_run_key": f"local:{run_id}",
            "source": source,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "status": status,
            "new_items": new_items,
            "error": error,
        }
        for run_id, source, started_at, finished_at, duration_seconds, status, new_items, error in rows
    ]


def upload_rows(
    supabase_url: str,
    service_role_key: str,
    table: str,
    conflict_column: str,
    rows: list[dict],
) -> None:
    """Upsert a set of public records using a server-only service-role key."""
    if not rows:
        return

    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/{table}"
        f"?on_conflict={conflict_column}"
    )
    payload = json.dumps(rows).encode("utf-8")
    upload_request = request.Request(
        endpoint,
        data=payload,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )

    try:
        with request.urlopen(upload_request, timeout=30) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"Supabase upload failed with HTTP {response.status}")
    except error.HTTPError as http_error:
        response_body = http_error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Supabase {table} upload failed with HTTP {http_error.code}: "
            f"{response_body}"
        ) from http_error


def upload_jobs(supabase_url: str, service_role_key: str, jobs: list[dict]) -> None:
    """Upsert jobs using a server-only Supabase service-role key."""
    upload_rows(supabase_url, service_role_key, "jobs", "source_url", jobs)


def upload_source_runs(
    supabase_url: str,
    service_role_key: str,
    source_runs: list[dict],
) -> None:
    """Upsert source health records using a server-only service-role key."""
    upload_rows(
        supabase_url,
        service_role_key,
        "source_runs",
        "source_run_key",
        source_runs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload collected jobs to Supabase.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = load_jobs(args.db)
    source_runs = load_source_runs(args.db)
    if args.dry_run:
        print(f"Would upload {len(jobs)} jobs and {len(source_runs)} source runs.")
        return

    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set."
        )

    upload_jobs(supabase_url, service_role_key, jobs)
    upload_source_runs(supabase_url, service_role_key, source_runs)
    print(f"Uploaded {len(jobs)} jobs and {len(source_runs)} source runs to Supabase.")


if __name__ == "__main__":
    main()
