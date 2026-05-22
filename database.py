import sqlite3
from contextlib import contextmanager
from typing import Iterator

from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    line_user_id TEXT PRIMARY KEY,
    display_name TEXT,
    location_1_lat REAL,
    location_1_lng REAL,
    location_1_name TEXT,
    location_2_lat REAL,
    location_2_lng REAL,
    location_2_name TEXT,
    onboard_complete INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS push_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_user_id TEXT,
    place_id TEXT,
    place_name TEXT,
    place_type TEXT,
    place_rating REAL,
    place_lat REAL,
    place_lng REAL,
    distance_meters INTEGER,
    meal_type TEXT,
    is_adhoc INTEGER DEFAULT 0,
    was_accepted INTEGER,
    swap_count INTEGER DEFAULT 0,
    weather_condition TEXT,
    pushed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_push_logs_user_time
    ON push_logs(line_user_id, pushed_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line_user_id TEXT,
    event_type TEXT,
    push_log_id INTEGER,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_user_time
    ON events(line_user_id, created_at);

CREATE TABLE IF NOT EXISTS user_exclusions (
    line_user_id TEXT,
    excluded_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (line_user_id, excluded_type)
);

CREATE TABLE IF NOT EXISTS user_blacklist (
    line_user_id TEXT,
    place_id TEXT,
    place_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (line_user_id, place_id)
);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
