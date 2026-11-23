"""SQLite storage and schema migrations for the opportunity agent."""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/agent.db")

INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id            INTEGER PRIMARY KEY,
    canonical_url TEXT UNIQUE NOT NULL,   -- first dedupe key
    title         TEXT NOT NULL,
    company       TEXT,
    type          TEXT,                   -- full-time / intern / contract / gig / research
    location      TEXT,
    remote        TEXT,                   -- remote-worldwide / remote-region-limited / india-ok / onsite-abroad
    posted_date   TEXT,
    deadline      TEXT,
    source        TEXT,
    score         REAL,                   -- filled by the LLM step (Milestone 3)
    first_seen    TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen     TEXT DEFAULT CURRENT_TIMESTAMP,
    emailed       INTEGER DEFAULT 0,
    description   TEXT
);
CREATE INDEX IF NOT EXISTS idx_title_company ON seen_items(company, title);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    sources_ok  INTEGER,
    sources_failed INTEGER,
    new_items   INTEGER,
    notes       TEXT
);
"""

SCORING_COLUMNS = {
    "llm_score": "REAL",
    "llm_reason": "TEXT",
    "llm_model": "TEXT",
    "final_score": "REAL",
    "practicality_score": "REAL",
    "opportunity_class": "TEXT",
    "practicality_reason": "TEXT",
}

SOURCE_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_runs (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    started_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_seconds REAL NOT NULL,
    status           TEXT NOT NULL CHECK(status IN ('ok', 'failed')),
    new_items        INTEGER NOT NULL DEFAULT 0,
    error            TEXT
);
CREATE INDEX IF NOT EXISTS idx_source_runs_source_started
    ON source_runs(source, started_at DESC);
"""

TELEGRAM_ALERTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_update_cursor (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    last_update_id INTEGER NOT NULL DEFAULT 0
);
"""

# Kept for collectors and tests that need an idempotent complete schema script.
SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id                  INTEGER PRIMARY KEY,
    canonical_url       TEXT UNIQUE NOT NULL,
    title               TEXT NOT NULL,
    company             TEXT,
    type                TEXT,
    location            TEXT,
    remote              TEXT,
    posted_date         TEXT,
    deadline            TEXT,
    source              TEXT,
    score               REAL,
    first_seen          TEXT DEFAULT CURRENT_TIMESTAMP,
    emailed             INTEGER DEFAULT 0,
    description         TEXT,
    llm_score           REAL,
    llm_reason          TEXT,
    llm_model           TEXT,
    final_score         REAL,
    practicality_score  REAL,
    opportunity_class   TEXT,
    practicality_reason TEXT,
    last_seen           TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_title_company ON seen_items(company, title);

CREATE TABLE IF NOT EXISTS runs (
    id             INTEGER PRIMARY KEY,
    started_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    sources_ok     INTEGER,
    sources_failed INTEGER,
    new_items      INTEGER,
    notes          TEXT
);
""" + SOURCE_RUNS_SCHEMA


def _apply_initial_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(INITIAL_SCHEMA)


def _add_scoring_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(seen_items)")
    }

    for name, definition in SCORING_COLUMNS.items():
        if name not in existing_columns:
            connection.execute(
                f"ALTER TABLE seen_items ADD COLUMN {name} {definition}"
            )


def _add_source_runs(connection: sqlite3.Connection) -> None:
    connection.executescript(SOURCE_RUNS_SCHEMA)


def _add_telegram_alert_state(connection: sqlite3.Connection) -> None:
    connection.executescript(TELEGRAM_ALERTS_SCHEMA)


def _add_last_seen_column(connection: sqlite3.Connection) -> None:
    """Record when a collector most recently observed each opportunity."""
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(seen_items)")
    }
    if "last_seen" not in existing_columns:
        connection.execute("ALTER TABLE seen_items ADD COLUMN last_seen TEXT")
    connection.execute(
        """
        UPDATE seen_items
        SET last_seen = COALESCE(last_seen, first_seen, CURRENT_TIMESTAMP)
        WHERE last_seen IS NULL
        """
    )


MIGRATIONS = (
    _apply_initial_schema,
    _add_scoring_columns,
    _add_source_runs,
    _add_telegram_alert_state,
    _add_last_seen_column,
)


def migrate(connection: sqlite3.Connection) -> None:
    """Apply every unapplied schema migration to an open SQLite connection."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied_versions = {
        row[0]
        for row in connection.execute("SELECT version FROM schema_migrations")
    }

    for version, migration in enumerate(MIGRATIONS, start=1):
        if version in applied_versions:
            continue
        migration(connection)
        connection.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)",
            (version,),
        )

    connection.commit()


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a database, creating or upgrading its schema as needed."""
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    migrate(connection)
    return connection

if __name__ == "__main__":
    connect().close()
    print(f"database ready at {DB_PATH}")
