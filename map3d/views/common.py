"""Shared helpers for the view blueprints."""

from __future__ import annotations

import functools
import logging
import time

from flask import Response, current_app, g, jsonify, request

from .. import services
from ..logging_setup import log_event
from ..maps import KIND_2D, KIND_3D, MapSpec, coords_have_distance

log = logging.getLogger("map3d.requests")


def json_error(message: str, status: int, **extra) -> tuple[Response, int]:
    payload = {
        "error": message,
        "request_id": getattr(g, "request_id", ""),
    }
    payload.update(extra)
    return jsonify(payload), status


def require_map(kind: str | None = None, allow_deprecated: bool = True):
    """Resolve ``<map_name>`` before the request body is parsed."""

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            name = kwargs.get("map_name", "")
            spec = services().registry.resolve(name)
            if spec is None:
                return json_error(
                    f'Invalid map name: "{name}". See /api/v2/maps for the list of '
                    "available maps.",
                    400,
                )
            if not allow_deprecated and spec.deprecated:
                return json_error(f'Map "{name}" is retired.', 410)
            if kind == KIND_3D and not spec.is_3d:
                return json_error(
                    f'Map "{spec.name}" is a 2D map and cannot be used here.',
                    400,
                )
            if kind == KIND_2D and spec.is_3d:
                return json_error(
                    f'Map "{spec.name}" is a 3D map and cannot be used here.',
                    400,
                )
            g.map_spec = spec
            return f(*args, **kwargs)

        return wrapper

    return decorator


def client_ip() -> str:
    return request.remote_addr or ""


def _limit_settings(kind: str) -> tuple[int, int, int]:
    cfg = current_app.config
    if kind == "interactive":
        return (
            cfg["RATE_LIMIT_INTERACTIVE_REQUESTS"],
            cfg["RATE_LIMIT_INTERACTIVE_WORK"],
            60,
        )
    if kind == "legacy":
        return (
            cfg["RATE_LIMIT_LEGACY_REQUESTS"],
            cfg["RATE_LIMIT_API_WORK"],
            cfg["RATE_LIMIT_WINDOW"],
        )
    return (
        cfg["RATE_LIMIT_API_REQUESTS"],
        cfg["RATE_LIMIT_API_WORK"],
        cfg["RATE_LIMIT_WINDOW"],
    )


def enforce_rate_limit(work: int, kind: str = "api") -> tuple[Response, int] | None:
    """Count this request against the client's budget; returns 429 if exceeded."""
    svc = services()
    requests_limit, work_limit, window = _limit_settings(kind)
    requested_work = max(0, int(work))

    key = f"{kind}:{svc.limiter.client_key(client_ip())}"
    result = svc.limiter.check(
        key,
        requests_limit=requests_limit,
        work_limit=work_limit,
        work=requested_work,
        window=window,
    )
    g.rate_limit = result

    if result.allowed:
        return None

    if result.exceeded == "work":
        message = (
            "This request would exceed your work-unit budget for this window "
            "(coordinates x samples x distance bins). Ask for fewer coordinates, "
            "a cheaper mode, or spread the queries over a longer period."
        )
    else:
        message = (
            "You are issuing too many queries in a short period of time. "
            "You can reduce the number of requests by asking for multiple "
            "coordinates (or distance bins) in a single call."
        )
    return json_error(
        message,
        429,
        exceeded=result.exceeded,
        limit=result.limit,
        remaining=result.remaining,
        work_limit=result.work_limit,
        work_remaining=result.work_remaining,
        requested_work=requested_work,
        retry_after=result.retry_after,
        reset_unix_time=result.reset,
    )


def load_query(spec: MapSpec):
    """Return (query_object, error_response)."""
    try:
        return services().registry.get(spec.name), None
    except FileNotFoundError as err:
        log.error("map data missing name=%s error=%s", spec.name, err)
        return None, json_error(
            f'The data for map "{spec.name}" is not available on this server.',
            503,
        )
    except Exception as err:
        log.exception("could not load map name=%s error=%s", spec.name, err)
        return None, json_error(f'The map "{spec.name}" could not be loaded.', 503)


def check_distance_support(spec: MapSpec, coords):
    if spec.requires_distance and not coords_have_distance(coords):
        return json_error(
            f'Map "{spec.name}" requires a distance for every coordinate (e.g. "d": 1.0).',
            400,
        )
    if not spec.supports_distance and coords_have_distance(coords):
        return json_error(
            f'Map "{spec.name}" is a 2D map; remove "d" from the request.',
            400,
        )
    return None


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.t0


def use_concurrency_slot():
    return services().concurrency.acquire()


def finish_request(
    *,
    map_name: str,
    endpoint: str,
    timer: Timer,
    n_coords: int,
    status: int,
    **fields,
):
    """Record anonymous statistics and emit one structured log line."""
    elapsed = timer.elapsed
    ip = client_ip()

    log_event(
        log,
        "query",
        request_id=getattr(g, "request_id", ""),
        endpoint=endpoint,
        map=map_name,
        status=status,
        n_coords=n_coords,
        seconds=elapsed,
        **fields,
    )

    if 200 <= status < 300:
        services().stats.record(
            map_name=map_name,
            endpoint=endpoint,
            ip=ip,
            n_coords=n_coords,
            seconds=elapsed,
        )
