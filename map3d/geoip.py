"""Offline IP → country/city lookup, evaluated per request and never stored.

Only the resolved country and a coarse grid cell are persisted (see
``usage_stats``); the IP itself is discarded when the request ends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeoLocation:
    country: str
    latitude: float | None = None
    longitude: float | None = None


UNKNOWN = GeoLocation(country="")


class GeoIPResolver:
    """Thin wrapper around a MaxMind-format (MMDB) city database.

    Works with the free DB-IP Lite City database as well as GeoLite2 City.
    A missing or unreadable database degrades to "unknown country" rather than
    failing requests.
    """

    def __init__(self, db_path: str | Path, enabled: bool = True):
        self.db_path = Path(db_path)
        self.enabled = enabled
        self._reader = None
        self._failed = False

    def _get_reader(self):
        if not self.enabled or self._failed:
            return None
        if self._reader is None:
            try:
                import geoip2.database

                self._reader = geoip2.database.Reader(str(self.db_path))
                log.info("geoip database loaded path=%s", self.db_path)
            except Exception as err:  # missing file, corrupt db, no geoip2
                self._failed = True
                log.warning("geoip unavailable path=%s error=%s", self.db_path, err)
                return None
        return self._reader

    @lru_cache(maxsize=4096)
    def lookup(self, ip: str) -> GeoLocation:
        reader = self._get_reader()
        if reader is None or not ip:
            return UNKNOWN
        try:
            record = reader.city(ip)
        except Exception:
            # AddressNotFoundError, or a non-IP value such as a Unix socket.
            return UNKNOWN
        country = (record.country.iso_code or "") if record.country else ""
        return GeoLocation(
            country=country,
            latitude=record.location.latitude,
            longitude=record.location.longitude,
        )
