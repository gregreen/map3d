"""Aggregate, non-identifying usage statistics.

For every query we persist only: the UTC day, the map, the endpoint, the country
and the integer-degree grid cell of the *resolved* client location, plus counts
and total time. No IP address, user agent, cookie, per-request row or exact
timestamp is stored, and the geography is resolved in memory and then discarded.
"""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass

from .db import Database
from .geoip import GeoIPResolver

log = logging.getLogger(__name__)

UNKNOWN_CELL = -1000


@dataclass(frozen=True)
class UsageRecord:
    day: str
    map: str
    endpoint: str
    country: str
    cell_lat: int
    cell_lon: int
    n_queries: int
    n_coords: int
    total_seconds: float


class UsageStats:
    def __init__(
        self,
        db: Database,
        geoip: GeoIPResolver,
        enabled: bool = True,
        retention_days: int = 730,
    ):
        self.db = db
        self.geoip = geoip
        self.enabled = enabled
        self.retention_days = retention_days

    def record(
        self,
        *,
        map_name: str,
        endpoint: str,
        ip: str | None,
        n_coords: int = 0,
        seconds: float = 0.0,
        now: float | None = None,
    ) -> None:
        if not self.enabled:
            return

        now = time.time() if now is None else now
        day = time.strftime("%Y-%m-%d", time.gmtime(now))

        country = ""
        cell_lat = cell_lon = UNKNOWN_CELL
        if ip:
            location = self.geoip.lookup(ip)
            country = location.country[:2]
            if location.latitude is not None and location.longitude is not None:
                cell_lat = int(location.latitude // 1)
                cell_lon = int(location.longitude // 1)

        try:
            with self.db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO usage_daily (
                        day, map, endpoint, country, cell_lat, cell_lon,
                        n_queries, n_coords, total_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT (day, map, endpoint, country, cell_lat, cell_lon)
                    DO UPDATE SET
                        n_queries = n_queries + 1,
                        n_coords = n_coords + excluded.n_coords,
                        total_seconds = total_seconds + excluded.total_seconds
                    """,
                    (
                        day,
                        map_name,
                        endpoint,
                        country,
                        cell_lat,
                        cell_lon,
                        int(n_coords),
                        float(seconds),
                    ),
                )
        except Exception as err:  # statistics must never break a query
            log.warning("usage stats write failed map=%s error=%s", map_name, err)

    def purge(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        cutoff = time.strftime(
            "%Y-%m-%d", time.gmtime(now - self.retention_days * 86400)
        )
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM usage_daily WHERE day < ?", (cutoff,))
            return cur.rowcount

    def totals(self, days: int = 30, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        cutoff = time.strftime("%Y-%m-%d", time.gmtime(now - days * 86400))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT map AS map,
                       SUM(n_queries) AS n_queries,
                       SUM(n_coords) AS n_coords,
                       SUM(total_seconds) AS total_seconds
                FROM usage_daily
                WHERE day >= ?
                GROUP BY map
                ORDER BY n_queries DESC
                """,
                (cutoff,),
            ).fetchall()
        return [
            {
                "map": row["map"],
                "n_queries": int(row["n_queries"] or 0),
                "n_coords": int(row["n_coords"] or 0),
                "total_seconds": round(float(row["total_seconds"] or 0.0), 3),
            }
            for row in rows
        ]

    def summary(self, days: int = 30, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else now
        cutoff = time.strftime("%Y-%m-%d", time.gmtime(now - days * 86400))
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT country, cell_lat, cell_lon,
                       SUM(n_queries) AS n_queries
                FROM usage_daily
                WHERE day >= ?
                GROUP BY country, cell_lat, cell_lon
                ORDER BY n_queries DESC
                """,
                (cutoff,),
            ).fetchall()
        return [
            {
                "country": row["country"],
                "cell_lat": row["cell_lat"],
                "cell_lon": row["cell_lon"],
                "n_queries": int(row["n_queries"] or 0),
            }
            for row in rows
        ]

    def export_csv(self, days: int = 365, now: float | None = None) -> str:
        now = time.time() if now is None else now
        cutoff = time.strftime("%Y-%m-%d", time.gmtime(now - days * 86400))
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "day",
                "map",
                "endpoint",
                "country",
                "cell_lat",
                "cell_lon",
                "n_queries",
                "n_coords",
                "total_seconds",
            ]
        )
        with self.db.connect() as conn:
            for row in conn.execute(
                """
                SELECT day, map, endpoint, country, cell_lat, cell_lon,
                       n_queries, n_coords, total_seconds
                FROM usage_daily
                WHERE day >= ?
                ORDER BY day, map, endpoint
                """,
                (cutoff,),
            ):
                writer.writerow([row[key] for key in row.keys()])
        return buffer.getvalue()
