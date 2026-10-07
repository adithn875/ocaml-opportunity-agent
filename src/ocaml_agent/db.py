"""SQLite storage. Two tables: seen_items (dedupe memory) and runs (run log)."""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/agent.db")

SCHEMA = """
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

def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con

if __name__ == "__main__":
    connect().close()
    print(f"database ready at {DB_PATH}")
