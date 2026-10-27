"""Interactive-page endpoints: line-of-sight curves, postage stamps, ASCII tables."""

from __future__ import annotations

import logging

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from flask import Blueprint, Response, current_app, g, jsonify

from ..loscurves import los_ascii_summary
from ..maps import KIND_3D, curve_distances, distance_moduli
from ..postage_stamp import RADIUS, encode_image
from ..utils import filter_NaN
from ..validators import skycoords_from_args, validate_qstring
from .common import (
    Timer,
    enforce_rate_limit,
    finish_request,
    json_error,
    load_query,
    require_map,
    use_concurrency_slot,
)

log = logging.getLogger(__name__)

bp = Blueprint("interactive", __name__, url_prefix="/api/v2/interactive")

INTERACTIVE_WORK = 200

# Points along the line of sight for maps that are queried distance by distance.
CURVE_POINTS = 64


def _finite_or_none(value, default):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if np.isfinite(value) else default


def _warning_for(spec, best, converged, infilled):
    """Wording for an unusable sightline, or None if the map is happy.

    The three cases are different things and each map reports them differently:
    a Bayestar or DECaPS sightline with no data at all (all-NaN profile) is
    outside the survey footprint, one whose fit failed inside the footprint is a
    non-convergence, and DECaPS additionally flags pixels infilled from their
    neighbors. The wording lives in the registry, since it names the survey.
    """
    covered = bool(np.any(np.isfinite(np.asarray(best, dtype="f8"))))
    if not covered:  # no data at all: outside the survey footprint
        return spec.no_coverage_warning or (spec.warning if converged is False else None)
    if converged is False:
        if infilled and spec.infilled_warning:
            return spec.infilled_warning
        return spec.warning
    return None


def _galactic(coords):
    if coords.frame.name == "galactic":
        return coords
    return coords.transform_to("galactic")


def _query_curve(spec, query_obj, coords):
    """Return (samples, best, distmod, flags) for a single line of sight.

    There are two shapes of map here. Bayestar and DECaPS answer a bare
    direction with a whole distance-reddening profile, so the plot can use
    their native distance bins. Edenhofer 2023 (and any map that needs a
    distance for every query) is asked at a subsampled set of distances along
    the line of sight instead.
    """
    if spec.requires_distance:
        distmod = curve_distances(query_obj, n_points=CURVE_POINTS)
        distances_pc = 10.0 ** (distmod / 5.0 + 1.0)
        coords3d = SkyCoord(
            coords.l,
            coords.b,
            distance=distances_pc * u.pc,
            frame="galactic",
        )
        best = np.asarray(query_obj(coords3d, mode=spec.default_mode))
        if not spec.supports_samples:
            return None, best, distmod, None
        # One posterior per distance, shaped (n_samples, n_distances) for the
        # plot, which is how the profile maps already return theirs.
        samples = np.asarray(query_obj(coords3d, mode="samples"))
        return np.moveaxis(samples, -1, 0), best, distmod, None

    if spec.supports_samples:
        samples, flags = query_obj(coords, mode="samples", return_flags=True)
        best_mode = "best" if "best" in spec.modes else "mean"
        best = query_obj(coords, mode=best_mode)
        distmod = distance_moduli(query_obj)
        return np.asarray(samples), np.asarray(best), distmod, flags

    # A map with a native distance grid but no samples: mean curve only.
    best = np.asarray(query_obj(coords, mode=spec.default_mode))
    return None, best, distance_moduli(query_obj), None


@bp.get("/<map_name>/losdata")
@require_map(kind=KIND_3D)
@validate_qstring("scalar-lonlat")
@skycoords_from_args()
def losdata(coords, map_name):
    spec = g.map_spec

    limited = enforce_rate_limit(work=INTERACTIVE_WORK, kind="interactive")
    if limited is not None:
        return limited

    query_obj, error = load_query(spec)
    if error is not None:
        return error

    timer = Timer()
    status = 200
    try:
        with use_concurrency_slot() as acquired:
            if not acquired:
                status = 503
                return json_error("The server is busy. Please retry shortly.", 503)

            coords = _galactic(coords)
            samples, best, distmod, flags = _query_curve(spec, query_obj, coords)
    except (ValueError, TypeError) as err:
        status = 400
        return json_error(str(err), 400)
    except Exception:
        status = 500
        log.exception("interactive query failed map=%s", spec.name)
        return json_error("The query failed unexpectedly.", 500)
    finally:
        finish_request(
            map_name=spec.name,
            endpoint="interactive/losdata",
            timer=timer,
            n_coords=1,
            status=status,
        )

    if samples is not None:
        samples = samples * spec.display_scale
    best = best * spec.display_scale

    converged = None
    infilled = None
    min_rel_dm = None
    max_rel_dm = None
    if flags is not None:
        converged = bool(np.all(flags["converged"]))
        if "infilled" in (flags.dtype.names or ()):
            infilled = bool(np.all(flags["infilled"]))
        min_rel_dm = _finite_or_none(flags["min_reliable_distmod"], 999.0)
        max_rel_dm = _finite_or_none(flags["max_reliable_distmod"], -999.0)

    warning = _warning_for(spec, best, converged, infilled)

    covered = bool(np.any(np.isfinite(best)))

    result = {
        "map": spec.name,
        "units": spec.display_units or spec.api_units,
        "success": bool(np.all(np.isfinite(best))),
        # False when the map has nothing at all for this direction, which for a
        # partial-coverage map means the sightline is outside its footprint.
        "in_footprint": covered,
        "l": float(coords.l.deg),
        "b": float(coords.b.deg),
        "radius": RADIUS,
        "distmod": np.asarray(distmod, dtype="f8").tolist(),
        "best": np.asarray(best, dtype="f8").tolist(),
        "samples": None if samples is None else np.asarray(samples, dtype="f8").tolist(),
        "has_samples": samples is not None,
        "converged": converged,
        "infilled": infilled,
        "warning": warning,
        "min_reliable_distmod": min_rel_dm,
        "max_reliable_distmod": max_rel_dm,
    }

    stamps = current_app.extensions["map3d"].stamps
    images = stamps.postage_stamps(spec.name, float(coords.l.deg), float(coords.b.deg))
    if images is None:
        result["images_available"] = False
    else:
        image = stamps.load(spec.name)
        labels = [f"{d:.0f} pc" for d in image.distances]
        result["images_available"] = True
        for k, (encoded, label) in enumerate(zip(images, labels)):
            result[f"label{k + 1:d}"] = label
            result[f"image{k + 1:d}"] = encode_image(encoded)

    return jsonify(filter_NaN(result))


@bp.get("/<map_name>/lostable")
@require_map(kind=KIND_3D)
@validate_qstring("scalar-lonlat")
@skycoords_from_args()
def lostable(coords, map_name):
    spec = g.map_spec

    limited = enforce_rate_limit(work=INTERACTIVE_WORK, kind="interactive")
    if limited is not None:
        return limited

    query_obj, error = load_query(spec)
    if error is not None:
        return error

    timer = Timer()
    status = 200
    try:
        coords = _galactic(coords)
        samples, best, distmod, flags = _query_curve(spec, query_obj, coords)
    except (ValueError, TypeError) as err:
        status = 400
        return json_error(str(err), 400)
    except Exception:
        status = 500
        log.exception("interactive table failed map=%s", spec.name)
        return json_error("The query failed unexpectedly.", 500)
    finally:
        finish_request(
            map_name=spec.name,
            endpoint="interactive/lostable",
            timer=timer,
            n_coords=1,
            status=status,
        )

    if samples is not None:
        samples = samples * spec.display_scale
    best = best * spec.display_scale

    table = los_ascii_summary(
        coords,
        samples,
        best,
        flags,
        distmod=np.asarray(distmod),
        encode=False,
        units=spec.display_units or spec.api_units,
        best_label="BestFit" if "best" in spec.modes else "Mean",
    )

    fname = f"{spec.name:s}_l_{coords.l.deg:.4f}_b_{coords.b.deg:.4f}.txt"
    return Response(
        table,
        mimetype="text/plain",
        headers={"Content-Disposition": f'inline; filename="{fname}"'},
    )
