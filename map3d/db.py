"""SQLite storage for rate-limit counters and aggregate usage statistics.

A single process-shared SQLite file (WAL mode) is enough for this workload:
a few counters per request and one upsert per query for the daily aggregate.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_limit (
    key          TEXT    NOT NULL,
    window_start INTEGER NOT NULL,
    requests     INTEGER NOT NULL,
    work         INTEGER NOT NULL,
    PRIMARY KEY (key, window_start)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS rate_limit_by_window ON rate_limit (window_start);

CREATE TABLE IF NOT EXISTS rate_limit_salt (
    day  TEXT PRIMARY KEY,
    salt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_daily (
    day           TEXT    NOT NULL,
    map           TEXT    NOT NULL,
    endpoint      TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    cell_lat      INTEGER NOT NULL,
    cell_lon      INTEGER NOT NULL,
    n_queries     INTEGER NOT NULL DEFAULT 0,
    n_coords      INTEGER NOT NULL DEFAULT 0,
    total_seconds REAL    NOT NULL DEFAULT 0,
    PRIMARY KEY (day, map, endpoint, country, cell_lat, cell_lon)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version (version) SELECT 1
    WHERE NOT EXISTS (SELECT 1 FROM schema_version);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._is_memory = self.path == ":memory:"

    def initialize(self) -> None:
        if not self._is_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=15.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 15000")
        if not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    @contextlib.contextmanager
    def connect(self):
        conn = self._new_connection()
        try:
            yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def transaction(self):
        """A short write transaction; retried once if the database is locked."""
        conn = self._new_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except sqlite3.OperationalError:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
            raise
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
