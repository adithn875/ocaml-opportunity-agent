"""Upload the locally collected jobs to Supabase's PostgREST API."""
import argparse
import json
import os
from pathlib import Path
from urllib import request

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


def upload_jobs(supabase_url: str, service_role_key: str, jobs: list[dict]) -> None:
    """Upsert jobs using a server-only Supabase service-role key."""
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/jobs?on_conflict=source_url"
    payload = json.dumps(jobs).encode("utf-8")
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

    with request.urlopen(upload_request, timeout=30) as response:
        if response.status not in (200, 201, 204):
            raise RuntimeError(f"Supabase upload failed with HTTP {response.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload collected jobs to Supabase.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    jobs = load_jobs(args.db)
    if args.dry_run:
        print(f"Would upload {len(jobs)} jobs.")
        return

    supabase_url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set."
        )

    upload_jobs(supabase_url, service_role_key, jobs)
    print(f"Uploaded {len(jobs)} jobs to Supabase.")


if __name__ == "__main__":
    main()
