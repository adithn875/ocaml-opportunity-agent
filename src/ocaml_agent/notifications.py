"""Create durable in-app notifications and optionally deliver browser push."""
import json
import os
from datetime import UTC, datetime

from .user_alerts import Supabase, matches_profile, now, parse_time


MAX_NOTIFICATIONS_PER_USER = 10


def notification_candidates(jobs, last_checked_at, profile, minimum_score):
    """Return recent jobs that meet one user's existing matching settings."""
    return [
        job
        for job in jobs
        if (parse_time(job.get("first_seen")) or now()) > last_checked_at
        and matches_profile(job, profile, minimum_score)
    ][:MAX_NOTIFICATIONS_PER_USER]


def create_inbox_notifications(supabase: Supabase, current_time: datetime | None = None) -> int:
    """Persist new matched jobs before attempting any delivery channel."""
    current_time = current_time or now()
    profiles = {
        row["user_id"]: row
        for row in supabase.select("user_profiles", {"select": "*"})
    }
    preferences = {
        row["user_id"]: row
        for row in supabase.select("alert_preferences", {"select": "*"})
    }
    states = {
        row["user_id"]: row
        for row in supabase.select("user_notification_states", {"select": "*"})
    }
    jobs = supabase.select(
        "jobs", {"select": "*", "order": "first_seen.desc", "limit": "200"}
    )
    created = 0

    for user_id in set(profiles) | set(preferences):
        state = states.get(user_id)
        if not state:
            # The user's first run establishes a baseline instead of sending old jobs.
            supabase.upsert(
                "user_notification_states",
                {"user_id": user_id, "last_checked_at": current_time.isoformat()},
            )
            continue
        last_checked_at = parse_time(state.get("last_checked_at")) or current_time
        preference = preferences.get(user_id, {})
        matches = notification_candidates(
            jobs,
            last_checked_at,
            profiles.get(user_id),
            float(preference.get("minimum_score") or 0),
        )
        for job in matches:
            supabase.upsert(
                "user_notifications", {"user_id": user_id, "job_id": job["id"]}
            )
            created += 1
        supabase.update(
            "user_notification_states",
            {"user_id": f"eq.{user_id}"},
            {"last_checked_at": current_time.isoformat()},
        )
    return created


def send_web_push(supabase: Supabase) -> int:
    """Deliver unsent inbox notifications when Web Push credentials are configured."""
    private_key = os.environ.get("VAPID_PRIVATE_KEY")
    subject = os.environ.get("VAPID_SUBJECT")
    if not private_key or not subject:
        print("Web Push disabled: VAPID_PRIVATE_KEY and VAPID_SUBJECT are not set.")
        return 0

    from pywebpush import WebPushException, webpush

    subscriptions = supabase.select("web_push_subscriptions", {"select": "*"})
    notifications = supabase.select(
        "user_notifications", {"select": "*", "push_sent_at": "is.null"}
    )
    jobs = {
        job["id"]: job
        for job in supabase.select("jobs", {"select": "id,title,company,source_url"})
    }
    delivered = 0

    for subscription in subscriptions:
        pending = [
            notification
            for notification in notifications
            if notification["user_id"] == subscription["user_id"] and notification["job_id"] in jobs
        ]
        if not pending:
            continue
        first_job = jobs[pending[0]["job_id"]]
        payload = json.dumps(
            {
                "title": "New OCaml opportunities",
                "body": f"{len(pending)} new match(es), including {first_job['title']}",
                "url": "https://ocaml-agent.pages.dev/#notifications",
            }
        )
        try:
            webpush(
                subscription_info=subscription["subscription"],
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
        except WebPushException as push_error:
            status = getattr(getattr(push_error, "response", None), "status_code", None)
            if status in {404, 410}:
                supabase.delete(
                    "web_push_subscriptions", {"endpoint": f"eq.{subscription['endpoint']}"}
                )
            continue
        for notification in pending:
            supabase.update(
                "user_notifications",
                {"id": f"eq.{notification['id']}"},
                {"push_sent_at": datetime.now(UTC).isoformat()},
            )
        delivered += len(pending)
    return delivered


def main() -> None:
    supabase = Supabase(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    )
    created = create_inbox_notifications(supabase)
    pushed = send_web_push(supabase)
    print(f"Notifications: {created} inbox records, {pushed} push deliveries.")


if __name__ == "__main__":
    main()
