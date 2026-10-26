"""Legacy v1 endpoints, kept working but deprecated.

They are superseded by ``/api/v2/<map>/query`` and emit ``Deprecation`` headers.
They will be removed once traffic drops to zero; see TODO.md.
"""

from __future__ import annotations

import logging

import numpy as np
from astropy import units as u
from flask import Blueprint, current_app, g, jsonify

from ..loscurves import los_ascii_summary
from ..postage_stamp import RADIUS, encode_image
from ..utils import filter_NaN
from ..validators import skycoords_from_args, validate_json, validate_qstring
from .common import (
    Timer,
    enforce_rate_limit,
    finish_request,
    json_error,
    load_query,
    use_concurrency_slot,
)

log = logging.getLogger(__name__)

bp = Blueprint("legacy", __name__)

DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Warning": '299 - "This endpoint is deprecated; use /api/v2/<map>/query"',
    "Link": '</api/v2/bayestar2019/query>; rel="alternate"',
}


def _sanitize_output(x, n_digits: int = 5):
    if isinstance(x, np.ndarray):
        if x.dtype.kind == "f":
            return np.round(x.astype(float), decimals=n_digits).tolist()
        return x.tolist()
    if isinstance(x, np.floating):
        return round(float(x), ndigits=n_digits)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _deprecated(response):
    for key, value in DEPRECATION_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


@bp.post("/gal-lb-query-light")
@validate_json("skycoord", "gal", "equ", "distance", "mode-legacy")
@skycoords_from_args()
def gal_lb_query_light(coords):
    mode = g.args.get("mode", "full")

    n_coords_max = {"full": 5000, "lite": 50000, "sfd": 500000}.get(mode)
    if n_coords_max is not None and g.n_coords > n_coords_max:
        return json_error(
            f'Too many coordinates requested: {g.n_coords} (max for mode "{mode}": {n_coords_max}).',
            413,
        )

    limited = enforce_rate_limit(work=g.n_coords, kind="legacy")
    if limited is not None:
        return limited

    registry = current_app.extensions["map3d"].registry
    timer = Timer()
    status = 200
    try:
        if mode in ("full", "lite"):
            spec = registry.spec("bayestar2015")
            query_obj, error = load_query(spec)
            if error is not None:
                return error
            if mode == "full":
                samples, flags = query_obj(coords, mode="samples", return_flags=True)
                best = query_obj(coords, mode="best", return_flags=False)
                res = {"samples": samples, "best": best}
            else:
                pctiles, flags = query_obj(
                    coords, mode="percentile", pct=[15.8, 50.0, 84.2], return_flags=True
                )
                best = query_obj(coords, mode="best", return_flags=False)
                res = {
                    "median": pctiles[..., 1],
                    "sigma": 0.5 * (pctiles[..., 2] - pctiles[..., 0]),
                    "best": best,
                }
            for key in flags.dtype.names:
                res[key] = flags[key]
            res["distmod"] = (query_obj.distmods / u.mag).decompose().value
        else:
            spec = registry.spec("sfd")
            query_obj, error = load_query(spec)
            if error is not None:
                return error
            res = {"EBV_SFD": query_obj(coords)}
    except (ValueError, TypeError) as err:
        status = 400
        return json_error(str(err), 400)
    except Exception:
        status = 500
        log.exception("legacy query failed mode=%s", mode)
        return json_error("An unexpected error occurred while executing the query.", 500)
    finally:
        finish_request(
            map_name="bayestar2015" if mode != "sfd" else "sfd",
            endpoint="legacy/gal-lb-query-light",
            timer=timer,
            n_coords=g.n_coords,
            status=status,
            mode=mode,
        )

    payload = {key: _sanitize_output(value) for key, value in res.items()}
    return _deprecated(jsonify(payload))


@bp.get("/gal-lb-query")
@validate_qstring("scalar-lonlat")
@skycoords_from_args()
def gal_lb_query(coords):
    limited = enforce_rate_limit(work=500, kind="interactive")
    if limited is not None:
        return limited

    registry = current_app.extensions["map3d"].registry
    spec = registry.spec("bayestar2015")
    query_obj, error = load_query(spec)
    if error is not None:
        return error

    if coords.frame.name != "galactic":
        coords = coords.transform_to("galactic")

    timer = Timer()
    status = 200
    try:
        with use_concurrency_slot() as acquired:
            if not acquired:
                status = 503
                return json_error("The server is busy. Please retry shortly.", 503)

            samples, flags = query_obj(coords, mode="samples", return_flags=True)
            best = query_obj(coords, mode="best")
            distmod = (query_obj.distmods / u.mag).decompose().value
            table = los_ascii_summary(coords, samples, best, flags, distmod=distmod)
            stamps = current_app.extensions["map3d"].stamps
            images = stamps.postage_stamps(
                spec.name, float(coords.l.deg), float(coords.b.deg)
            )
    except (ValueError, TypeError) as err:
        status = 400
        return json_error(str(err), 400)
    except Exception:
        status = 500
        log.exception("legacy interactive query failed")
        return json_error("The query failed unexpectedly.", 500)
    finally:
        finish_request(
            map_name=spec.name,
            endpoint="legacy/gal-lb-query",
            timer=timer,
            n_coords=g.n_coords,
            status=status,
        )

    res = filter_NaN(
        {
            "success": bool(np.all(np.isfinite(best))),
            "l": float(coords.l.deg),
            "b": float(coords.b.deg),
            "radius": RADIUS,
            "table": table,
            "samples": np.asarray(samples).tolist(),
            "best": np.asarray(best).tolist(),
            "distmod": np.asarray(distmod).tolist(),
            "converged": bool(np.all(flags["converged"])),
            "min_reliable_distmod": float(flags["min_reliable_distmod"]),
            "max_reliable_distmod": float(flags["max_reliable_distmod"]),
        }
    )

    if images is not None:
        labels = [f"{d:.0f} pc" for d in stamps.load(spec.name).distances]
        for k, (encoded, label) in enumerate(zip(images, labels)):
            res[f"label{k + 1:d}"] = label
            res[f"image{k + 1:d}"] = encode_image(encoded)

    return _deprecated(jsonify(res))
