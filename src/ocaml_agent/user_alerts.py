"""Link Telegram users and send them newly matched opportunities."""
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib import parse, request

from .telegram import send_long_message_to_chat


DB_PATH = Path("data/agent.db")
MAX_ALERT_JOBS = 10
BOT_START_PREFIX = "ocamljobs_"


def now() -> datetime:
    return datetime.now(UTC)


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_json(url: str, headers: dict[str, str], method: str = "GET", body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    api_request = request.Request(url, data=data, headers=headers, method=method)
    with request.urlopen(api_request, timeout=30) as response:
        content = response.read().decode("utf-8")
    return json.loads(content) if content else None


class Supabase:
    def __init__(self, base_url: str, service_role_key: str):
        self.base_url = base_url.rstrip("/") + "/rest/v1"
        self.headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    def select(self, table: str, query: dict[str, str]):
        return fetch_json(
            f"{self.base_url}/{table}?{parse.urlencode(query)}",
            self.headers,
        )

    def upsert(self, table: str, row: dict):
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
        return fetch_json(
            f"{self.base_url}/{table}", headers, "POST", row
        )

    def delete(self, table: str, query: dict[str, str]):
        return fetch_json(
            f"{self.base_url}/{table}?{parse.urlencode(query)}",
            self.headers,
            "DELETE",
        )

    def update(self, table: str, query: dict[str, str], row: dict):
        return fetch_json(
            f"{self.base_url}/{table}?{parse.urlencode(query)}",
            self.headers,
            "PATCH",
            row,
        )


def current_update_id(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT last_update_id FROM telegram_update_cursor WHERE id = 1"
    ).fetchone()
    return row[0] if row else 0


def save_update_id(connection: sqlite3.Connection, update_id: int) -> None:
    connection.execute(
        """
        INSERT INTO telegram_update_cursor (id, last_update_id) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET last_update_id = excluded.last_update_id
        """,
        (update_id,),
    )
    connection.commit()


def telegram_updates(token: str, offset: int) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=0"
    result = fetch_json(url, {})
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")
    return result["result"]


def process_link_updates(connection: sqlite3.Connection, supabase: Supabase, token: str) -> int:
    """Convert valid /start link commands into private user subscriptions."""
    updates = telegram_updates(token, current_update_id(connection) + 1)
    newest_update_id = current_update_id(connection)
    linked = 0

    for update in updates:
        newest_update_id = max(newest_update_id, update["update_id"])
        message = update.get("message") or {}
        text = message.get("text", "")
        if not text.startswith(f"/start {BOT_START_PREFIX}"):
            continue
        link_token = text.removeprefix(f"/start {BOT_START_PREFIX}").strip()
        matches = supabase.select(
            "telegram_link_tokens",
            {"select": "user_id,expires_at", "token": f"eq.{link_token}"},
        )
        if len(matches) != 1 or (parse_time(matches[0]["expires_at"]) or now()) < now():
            continue

        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            continue
        supabase.upsert(
            "telegram_subscriptions",
            {
                "user_id": matches[0]["user_id"],
                "chat_id": chat_id,
                "enabled": True,
                "linked_at": now().isoformat(),
                "last_checked_at": now().isoformat(),
            },
        )
        supabase.delete("telegram_link_tokens", {"token": f"eq.{link_token}"})
        linked += 1

    if newest_update_id > current_update_id(connection):
        save_update_id(connection, newest_update_id)
    return linked


def is_due(subscription: dict, frequency: str, current_time: datetime) -> bool:
    last_checked = parse_time(subscription.get("last_checked_at"))
    if not last_checked:
        return True
    interval = timedelta(days=7 if frequency == "weekly" else 1)
    return current_time >= last_checked + interval


def matches_profile(job: dict, profile: dict | None, minimum_score: float) -> bool:
    try:
        score = float(job.get("final_score") or 0)
    except (TypeError, ValueError):
        score = 0
    profile = profile or {}
    if score < max(minimum_score, float(profile.get("minimum_score") or 0)):
        return False

    text = " ".join(
        str(job.get(field) or "")
        for field in ("title", "company", "description", "location", "source")
    ).lower()
    skills = [skill.lower() for skill in profile.get("skills", []) if skill]
    if skills and not any(skill in text for skill in skills):
        return False

    remote_preference = profile.get("remote_preference", "any")
    remote = str(job.get("remote") or "").lower()
    if remote_preference == "remote" and "remote" not in remote:
        return False
    if remote_preference == "onsite" and "remote" in remote:
        return False

    locations = [location.lower() for location in profile.get("locations", []) if location]
    return not locations or any(location in text for location in locations)


def build_alert(jobs: list[dict]) -> str:
    lines = ["🔔 New OCaml opportunities", ""]
    for job in jobs:
        lines.append(f"• {job['title']}")
        details = " · ".join(
            str(value) for value in (job.get("company"), job.get("location")) if value
        )
        if details:
            lines.append(details)
        lines.append(f"Match score: {float(job.get('final_score') or 0):.0f}")
        lines.append(job["source_url"])
        lines.append("")
    return "\n".join(lines).strip()


def send_due_alerts(supabase: Supabase, current_time: datetime | None = None) -> int:
    """Send due subscriptions only jobs found since their last check."""
    current_time = current_time or now()
    subscriptions = supabase.select(
        "telegram_subscriptions", {"select": "*", "enabled": "eq.true"}
    )
    preferences = {
        row["user_id"]: row
        for row in supabase.select("alert_preferences", {"select": "*"})
    }
    profiles = {
        row["user_id"]: row
        for row in supabase.select("user_profiles", {"select": "*"})
    }
    jobs = supabase.select(
        "jobs", {"select": "*", "order": "first_seen.desc", "limit": "200"}
    )
    delivered = 0

    for subscription in subscriptions:
        preference = preferences.get(subscription["user_id"], {})
        if not is_due(subscription, preference.get("frequency", "daily"), current_time):
            continue
        last_checked = parse_time(subscription.get("last_checked_at"))
        matches = [
            job
            for job in jobs
            if (not last_checked or (parse_time(job.get("first_seen")) or current_time) > last_checked)
            and matches_profile(job, profiles.get(subscription["user_id"]), float(preference.get("minimum_score") or 0))
        ][:MAX_ALERT_JOBS]
        if matches:
            send_long_message_to_chat(subscription["chat_id"], build_alert(matches))
            delivered += 1
        supabase.update(
            "telegram_subscriptions",
            {"user_id": f"eq.{subscription['user_id']}"},
            {
                "last_checked_at": current_time.isoformat(),
                **({"last_sent_at": current_time.isoformat()} if matches else {}),
            },
        )
    return delivered


def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"]
    service_role_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
    with sqlite3.connect(DB_PATH) as connection:
        linked = process_link_updates(connection, Supabase(supabase_url, service_role_key), telegram_token)
    delivered = send_due_alerts(Supabase(supabase_url, service_role_key))
    print(f"Telegram alerts: {linked} linked, {delivered} delivered.")


if __name__ == "__main__":
    main()
