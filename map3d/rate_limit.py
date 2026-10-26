"""Rate limiting backed by SQLite.

Two budgets are enforced per client and window: a request count, and weighted
*work units* (coordinate count × samples × distance bins) so that one very
large request costs as much as many small ones.

Clients are identified by an HMAC of their IP prefix with a daily salt that is
stored in the database (shared by all workers) but never logged. The plain IP
is never written to disk.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import ipaddress
import logging
import secrets
import threading
import time
from dataclasses import dataclass

from .db import Database

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int
    retry_after: int


def ip_prefix(ip: str) -> str:
    """Normalize an address for bucketing: IPv4 as-is, IPv6 by /64 network."""
    try:
        addr = ipaddress.ip_address(ip.split("%", 1)[0])
    except ValueError:
        return ip or "unknown"
    if addr.version == 6:
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def salted_key(ip: str, salt: str) -> str:
    return hmac.new(
        salt.encode("utf-8"), ip_prefix(ip).encode("utf-8"), hashlib.sha256
    ).hexdigest()


class RateLimiter:
    def __init__(self, db: Database):
        self.db = db
        self._calls = 0
        self._calls_lock = threading.Lock()

    def salt_for(self, day: str) -> str:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT salt FROM rate_limit_salt WHERE day = ?", (day,)
            ).fetchone()
            if row is not None:
                return row["salt"]
            salt = secrets.token_hex(16)
            conn.execute(
                "INSERT OR IGNORE INTO rate_limit_salt (day, salt) VALUES (?, ?)",
                (day, salt),
            )
            return salt

    def client_key(self, ip: str, now: float | None = None) -> str:
        now = time.time() if now is None else now
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        return salted_key(ip, self.salt_for(day))

    def check(
        self,
        key: str,
        *,
        requests_limit: int,
        work_limit: int,
        work: int = 0,
        cost: int = 1,
        window: int = 300,
        now: float | None = None,
    ) -> LimitResult:
        now = time.time() if now is None else now
        window_start = int(now // window) * window
        reset = window_start + window
        retry_after = max(1, int(reset - now))

        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT requests, work FROM rate_limit WHERE key = ? AND window_start = ?",
                (key, window_start),
            ).fetchone()
            used_requests = row["requests"] if row else 0
            used_work = row["work"] if row else 0

            allowed = (
                used_requests + cost <= requests_limit
                and used_work + work <= work_limit
            )
            if allowed:
                conn.execute(
                    """
                    INSERT INTO rate_limit (key, window_start, requests, work)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (key, window_start) DO UPDATE SET
                        requests = requests + excluded.requests,
                        work = work + excluded.work
                    """,
                    (key, window_start, cost, work),
                )
                used_requests += cost
                used_work += work

            self._maybe_purge(conn, window_start)

        return LimitResult(
            allowed=allowed,
            limit=requests_limit,
            remaining=max(0, requests_limit - used_requests),
            reset=reset,
            retry_after=retry_after,
        )

    def _maybe_purge(self, conn, window_start: int) -> None:
        with self._calls_lock:
            self._calls += 1
            due = self._calls % 500 == 0
        if due:
            conn.execute(
                "DELETE FROM rate_limit WHERE window_start < ?", (window_start - 3600,)
            )

    def purge(self, before: int | None = None) -> int:
        cutoff = before if before is not None else int(time.time()) - 3600
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM rate_limit WHERE window_start < ?", (cutoff,)
            )
            return cur.rowcount


class ConcurrencyGuard:
    """Bounds simultaneous expensive queries within a worker process."""

    def __init__(self, size: int, timeout: float):
        self.size = max(1, size)
        self.timeout = timeout
        self._semaphore = threading.BoundedSemaphore(self.size)

    @contextlib.contextmanager
    def acquire(self):
        acquired = self._semaphore.acquire(timeout=self.timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self._semaphore.release()
