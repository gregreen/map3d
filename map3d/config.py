"""Application configuration.

Everything that differs between a developer laptop, the test suite and the
AWS deployment is read from the environment here, so the same image can run
anywhere without code changes.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default):
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    return int(_env(name, default))


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    return float(_env(name, default))


def dustmaps_data_dir() -> Path:
    """The directory dustmaps uses for map files (honours ~/.dustmapsrc)."""
    from dustmaps.std_paths import data_dir

    return Path(data_dir())


def default_config() -> dict:
    data_dir = Path(_env("MAP3D_DATA_DIR", dustmaps_data_dir()))
    state_dir = Path(_env("MAP3D_STATE_DIR", REPO_ROOT / "var"))

    return {
        # Data
        "DATA_DIR": str(data_dir),
        "IMAGES_DIR": str(Path(_env("MAP3D_IMAGES_DIR", data_dir / "images"))),
        "STATE_DIR": str(state_dir),
        "SQLITE_PATH": str(Path(_env("MAP3D_SQLITE_PATH", state_dir / "map3d.sqlite3"))),
        "GEOIP_DB": str(Path(_env("MAP3D_GEOIP_DB", state_dir / "dbip-city-lite.mmdb"))),
        "GEOIP_ENABLED": _env_bool("MAP3D_GEOIP_ENABLED", True),
        # Maps
        "MAX_SAMPLES": _env_int("MAP3D_MAX_SAMPLES", 5),
        "STAMP_NSIDE": _env_int("MAP3D_STAMP_NSIDE", 512),
        "IMAGE_CACHE_SIZE": _env_int("MAP3D_IMAGE_CACHE_SIZE", 4),
        "ENABLED_MAPS": [
            m.strip()
            for m in _env("MAP3D_ENABLED_MAPS", "").split(",")
            if m.strip()
        ],
        # Request limits
        "MAX_CONTENT_LENGTH": _env_int("MAP3D_MAX_CONTENT_LENGTH", 8 * 1024 * 1024),
        "MAX_OUTPUT_VALUES": _env_int("MAP3D_MAX_OUTPUT_VALUES", 1_000_000),
        "MAX_COORDS": _env_int("MAP3D_MAX_COORDS", 500_000),
        "GLOBAL_CONCURRENCY": _env_int("MAP3D_GLOBAL_CONCURRENCY", 8),
        "CONCURRENCY_TIMEOUT": _env_float("MAP3D_CONCURRENCY_TIMEOUT", 10.0),
        # Rate limiting: (requests, work units) per window, per client
        "RATE_LIMIT_WINDOW": _env_int("MAP3D_RATE_LIMIT_WINDOW", 300),
        "RATE_LIMIT_API_REQUESTS": _env_int("MAP3D_RATE_LIMIT_API_REQUESTS", 300),
        "RATE_LIMIT_API_WORK": _env_int("MAP3D_RATE_LIMIT_API_WORK", 1_000_000),
        "RATE_LIMIT_INTERACTIVE_REQUESTS": _env_int(
            "MAP3D_RATE_LIMIT_INTERACTIVE_REQUESTS", 30
        ),
        "RATE_LIMIT_INTERACTIVE_WORK": _env_int(
            "MAP3D_RATE_LIMIT_INTERACTIVE_WORK", 100_000
        ),
        "RATE_LIMIT_LEGACY_REQUESTS": _env_int("MAP3D_RATE_LIMIT_LEGACY_REQUESTS", 1000),
        # Statistics
        "USAGE_STATS_ENABLED": _env_bool("MAP3D_USAGE_STATS_ENABLED", True),
        "USAGE_RETENTION_DAYS": _env_int("MAP3D_USAGE_RETENTION_DAYS", 730),
        # Deployment
        "TRUSTED_PROXY_HOPS": _env_int("MAP3D_TRUSTED_PROXY_HOPS", 1),
        "ENABLE_LEGACY_API": _env_bool("MAP3D_ENABLE_LEGACY_API", True),
        "LOG_LEVEL": _env("MAP3D_LOG_LEVEL", "INFO"),
        "JSON_SORT_KEYS": False,
        "TMP_DIR": _env("MAP3D_TMP_DIR", tempfile.gettempdir()),
    }
