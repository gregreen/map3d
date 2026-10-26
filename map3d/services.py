"""Long-lived application services, built once per process."""

from __future__ import annotations

from dataclasses import dataclass

from .db import Database
from .geoip import GeoIPResolver
from .maps import MapRegistry, build_registry
from .postage_stamp import StampImageStore
from .rate_limit import ConcurrencyGuard, RateLimiter
from .usage_stats import UsageStats


@dataclass
class Services:
    registry: MapRegistry
    db: Database
    limiter: RateLimiter
    concurrency: ConcurrencyGuard
    stats: UsageStats
    geoip: GeoIPResolver
    stamps: StampImageStore


def build_services(config) -> Services:
    db = Database(config["SQLITE_PATH"])
    db.initialize()

    geoip = GeoIPResolver(config["GEOIP_DB"], enabled=config["GEOIP_ENABLED"])
    stats = UsageStats(
        db,
        geoip,
        enabled=config["USAGE_STATS_ENABLED"],
        retention_days=config["USAGE_RETENTION_DAYS"],
    )

    registry = config.get("REGISTRY") or build_registry(config)

    return Services(
        registry=registry,
        db=db,
        limiter=RateLimiter(db),
        concurrency=ConcurrencyGuard(
            config["GLOBAL_CONCURRENCY"], config["CONCURRENCY_TIMEOUT"]
        ),
        stats=stats,
        geoip=geoip,
        stamps=StampImageStore(config["IMAGES_DIR"], config["IMAGE_CACHE_SIZE"]),
    )
