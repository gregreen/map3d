"""Public query API (``/api/v2``).

The request/response format is fixed by ``dustmaps.bayestar.BayestarWebQuery``:
a JSON POST whose body is decoded with ``MultiJSONDecoder``, and a response
encoded with ``MultiJSONEncoder`` (base64 arrays, tagged SkyCoord/Quantity).
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request, url_for

from ..maps import output_size
from ..validators import ExtendedValidator, skycoords_from_args, validate_json
from .common import (
    Timer,
    check_distance_support,
    enforce_rate_limit,
    finish_request,
    json_error,
    load_query,
    require_map,
    use_concurrency_slot,
)

log = logging.getLogger(__name__)

bp = Blueprint("api_v2", __name__, url_prefix="/api/v2")


@bp.post("/<map_name>/query")
@require_map()
@validate_json(
    "skycoord",
    "gal",
    "equ",
    "distance",
    "equ-frame",
    allow_unknown=True,
)
@skycoords_from_args()
def query(coords, map_name):
    spec = g.map_spec
    cfg = current_app.config

    kwargs = dict(g.args or {})
    if spec.schema:
        validator = ExtendedValidator(spec.schema, allow_unknown=False)
        if not validator.validate(kwargs):
            return json_error("Invalid keyword arguments.", 400, input_errors=validator.errors)
        kwargs = dict(validator.document)
    elif kwargs:
        return json_error(
            f'Map "{spec.name}" accepts no additional keyword arguments.',
            400,
            input_errors={"unknown": sorted(kwargs)},
        )

    distance_error = check_distance_support(spec, coords)
    if distance_error is not None:
        return distance_error

    if g.n_coords > cfg["MAX_COORDS"]:
        return json_error(
            "Too many coordinates requested: {} (max {}).".format(
                g.n_coords, cfg["MAX_COORDS"]
            ),
            413,
        )

    query_obj, error = load_query(spec)
    if error is not None:
        return error

    size = output_size(query_obj, spec, coords, kwargs)
    if size > cfg["MAX_OUTPUT_VALUES"]:
        return json_error(
            "Requested output is too large (requested: {}, max: {}).".format(
                size, cfg["MAX_OUTPUT_VALUES"]
            ),
            413,
            requested_size=size,
            max_size=cfg["MAX_OUTPUT_VALUES"],
        )

    limited = enforce_rate_limit(work=size, kind="api")
    if limited is not None:
        return limited

    timer = Timer()
    status = 200
    with use_concurrency_slot() as acquired:
        if not acquired:
            status = 503
            return json_error(
                "The server is busy with other queries. Please retry shortly.", 503
            )
        try:
            result = query_obj(coords, **kwargs)
        except (ValueError, TypeError) as err:
            status = 400
            log.info(
                "query rejected request_id=%s map=%s error=%s",
                getattr(g, "request_id", ""),
                spec.name,
                err,
            )
            return json_error(str(err), 400)
        except Exception as err:
            status = 500
            log.exception(
                "query failed request_id=%s map=%s",
                getattr(g, "request_id", ""),
                spec.name,
            )
            return json_error(
                f"An unexpected error occurred while executing the query ({type(err).__name__}).",
                500,
            )
        finally:
            finish_request(
                map_name=spec.name,
                endpoint="api/v2/query",
                timer=timer,
                n_coords=g.n_coords,
                status=status,
            )

    return jsonify(result)


@bp.get("/maps")
def maps():
    svc = current_app.extensions["map3d"]
    metadata = svc.registry.public_metadata()
    images = set(svc.stamps.available_maps())
    for name, entry in metadata.items():
        entry["query_url"] = url_for("api_v2.query", map_name=name, _external=False)
        entry["interactive"] = entry["kind"] == "3d" and name in images
        entry["stamp_images_available"] = name in images
    return jsonify(
        {
            "maps": metadata,
            "count": len(metadata),
            "max_samples": current_app.config["MAX_SAMPLES"],
            "max_output_values": current_app.config["MAX_OUTPUT_VALUES"],
        }
    )


@bp.get("/stats")
def stats():
    days = request.args.get("days", "30")
    try:
        days = max(1, min(365, int(days)))
    except (TypeError, ValueError):
        return json_error("'days' must be an integer.", 400)

    svc = current_app.extensions["map3d"]
    return jsonify(
        {
            "window_days": days,
            "maps": svc.stats.totals(days=days),
            "note": (
                "Aggregate counts only; no client identifiers or per-request "
                "records are stored."
            ),
        }
    )


@bp.get("/openapi.json")
def openapi():
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Argonaut dust map API",
            "version": "2.0",
            "description": (
                "Query 2D and 3D interstellar dust maps. Coordinates may be "
                "given as Galactic (l, b), Equatorial (ra, dec), or as a "
                "dustmaps-serialised SkyCoord. Arrays are base64-encoded."
            ),
        },
        "servers": [{"url": "/api/v2"}],
        "paths": {
            "/{map}/query": {
                "post": {
                    "summary": "Query a dust map",
                    "parameters": [
                        {
                            "name": "map",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Map name; see /api/v2/maps.",
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "l": {"type": "number", "description": "Galactic longitude (deg)"},
                                        "b": {"type": "number", "description": "Galactic latitude (deg)"},
                                        "ra": {"type": "number", "description": "Right ascension (deg)"},
                                        "dec": {"type": "number", "description": "Declination (deg)"},
                                        "d": {
                                            "oneOf": [
                                                {"type": "number"},
                                                {"type": "array", "items": {"type": "number"}},
                                            ],
                                            "description": "Distance (kpc)",
                                        },
                                        "frame": {"type": "string", "enum": ["icrs", "fk5", "fk4"]},
                                        "coords": {
                                            "type": "object",
                                            "description": "Dustmaps-serialised SkyCoord",
                                        },
                                        "mode": {"type": "string"},
                                        "pct": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                            "description": "Percentiles, when mode='percentile'",
                                        },
                                        "return_flags": {"type": "boolean"},
                                        "seed_or_rng": {
                                            "type": "integer",
                                            "minimum": 0,
                                            "description": (
                                                "Seed for the random modes. An integer only; "
                                                "numpy generators are not accepted."
                                            ),
                                        },
                                        "order": {"type": "integer", "description": "SFD interpolation order"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {"description": "Query result"},
                        "400": {"description": "Invalid map name or arguments"},
                        "413": {"description": "Requested output too large"},
                        "429": {"description": "Rate limit exceeded"},
                        "503": {"description": "Server busy or map data unavailable"},
                    },
                }
            },
            "/maps": {"get": {"summary": "List available maps", "responses": {"200": {"description": "Map metadata"}}}},
            "/stats": {"get": {"summary": "Aggregate query counts", "responses": {"200": {"description": "Totals per map"}}}},
        },
        "components": {
            "schemas": {
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                }
            }
        },
    }
    return jsonify(spec)

