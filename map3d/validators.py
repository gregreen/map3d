"""Request validation for the query APIs.

The schemas are unchanged in spirit from the original service: coordinates may be
given as a (dustmaps-serialised) ``SkyCoord``, as Galactic/Equatorial angles, or
as a Galactic/Equatorial pair in a query string. Map-specific keyword arguments
are validated by the per-map schema in :mod:`map3d.maps`.
"""

from __future__ import annotations

import functools
import json
import warnings

import numpy as np
from astropy import units
from astropy.coordinates import SkyCoord
from astropy.units import Quantity
from cerberus import Validator
from dustmaps import json_serializers
from flask import Response, g, request


def to_array(dtype):
    def f(value):
        return np.array(value, dtype=dtype)

    return f


def to_quantity(unit_spec, dtype="f8"):
    def f(value):
        if value is None:
            return None
        if isinstance(value, Quantity):
            return value.to(unit_spec)
        if isinstance(value, np.ndarray):
            return value.astype(dtype) * unit_spec
        return np.array(value, dtype=dtype) * unit_spec

    return f


with warnings.catch_warnings():
    # Cerberus warns for rules that take no arguments; we use several of them.
    warnings.filterwarnings("ignore", message="No validation schema")

    class ExtendedValidator(Validator):
        def _validate_type_skycoord(self, value):
            return isinstance(value, SkyCoord)

        def _validate_type_numberlike_ndarray(self, value):
            if isinstance(value, np.ndarray):
                return value.dtype.kind in "iuf"
            return False

        def _validate_type_quantity(self, value):
            return isinstance(value, Quantity)

        def _validate_type_angle(self, value):
            return isinstance(value, Quantity) and value.unit.is_equivalent(units.rad)

        def _validate_type_length(self, value):
            return isinstance(value, Quantity) and value.unit.is_equivalent(units.m)

        def _validate_type_scalar(self, value):
            if isinstance(value, (float, int, np.floating, np.integer)):
                return True
            return isinstance(value, Quantity) and value.isscalar

        def _validate_type_list_of_numbers(self, value):
            if not isinstance(value, (list, tuple)):
                return False
            return all(isinstance(el, (float, int)) for el in value)

        def _validate_type_np_number(self, value):
            return isinstance(value, (np.floating, np.integer))

        def _validate_maxall(self, max_val, field, value):
            """Test whether all the elements of an array are less than a given amount.

            The rule's arguments are validated against this schema:
            {}
            """
            if np.any(value > max_val):
                self._error(field, f"Must not be greater than {max_val}")

        def _validate_minall(self, min_val, field, value):
            """Test whether all the elements of an array are greater than a given amount.

            The rule's arguments are validated against this schema:
            {}
            """
            if np.any(value < min_val):
                self._error(field, f"Must not be less than {min_val}")

        def _validate_sameshape(self, target_field, field, value):
            """Test whether this field has the same shape as one or more other fields.

            The rule's arguments are validated against this schema:
            {'type': ['string', 'list']}
            """
            if isinstance(target_field, str):
                target_field = [target_field]
            shape = value.shape
            for target in target_field:
                res = self._lookup_field(target)[1]
                if res is None:
                    return True
                if not hasattr(res, "shape"):
                    self._error(field, f"Must have same shape as {target}, which has no shape.")
                elif res.shape != shape:
                    self._error(field, f"Must have same shape as {target}.")
            return True


common_validators = {
    "skycoord": {
        "coords": {
            "type": "skycoord",
            "excludes": ["l", "b", "ra", "dec", "d"],
        },
    },
    "gal": {
        "l": {
            "coerce": to_quantity(units.deg),
            "type": "angle",
            "excludes": ["coords", "ra", "dec"],
            "dependencies": "b",
            "sameshape": "b",
        },
        "b": {
            "coerce": to_quantity(units.deg),
            "type": "angle",
            "maxall": 90.0 * units.deg,
            "minall": -90.0 * units.deg,
            "excludes": ["coords", "ra", "dec"],
            "dependencies": "l",
        },
    },
    "equ": {
        "ra": {
            "coerce": to_quantity(units.deg),
            "type": "angle",
            "excludes": ["coords", "l", "b"],
            "dependencies": "dec",
            "sameshape": "dec",
        },
        "dec": {
            "coerce": to_quantity(units.deg),
            "type": "angle",
            "maxall": 90.0 * units.deg,
            "minall": -90.0 * units.deg,
            "excludes": ["coords", "l", "b"],
            "dependencies": "ra",
        },
    },
    "distance": {
        "d": {
            "required": False,
            "coerce": to_quantity(units.kpc),
            "type": "length",
            "excludes": "coords",
            "minall": 0.0 * units.kpc,
            "nullable": True,
            "anyof": [
                {"sameshape": "l"},
                {"sameshape": "ra"},
                {"type": "scalar"},
            ],
        }
    },
    "mode-legacy": {
        "mode": {
            "required": False,
            "type": "string",
            "allowed": ["full", "lite", "sfd"],
            "default": "full",
        }
    },
    "equ-frame": {
        "frame": {
            "required": False,
            "type": "string",
            "allowed": ["icrs", "fk5", "fk4", "fk4noeterms"],
            "excludes": ["coords", "l", "b"],
        }
    },
    "scalar-lonlat": {
        "lon": {
            "required": True,
            "coerce": to_quantity(units.deg),
            "allof": [{"type": "scalar"}, {"type": "angle"}],
        },
        "lat": {
            "required": True,
            "coerce": to_quantity(units.deg),
            "allof": [{"type": "scalar"}, {"type": "angle"}],
            "min": -90.0 * units.deg,
            "max": 90.0 * units.deg,
        },
        "coordsys": {
            "required": True,
            "type": "string",
            "allowed": ["gal", "equ"],
        },
    },
}


def get_validator(*args, **kwargs):
    """Combine one or more of the schemata in :obj:`common_validators`."""
    schema = {}
    for name in args:
        schema.update(common_validators[name])
    return ExtendedValidator(schema, **kwargs)


def _error_response(errors, status: int = 400) -> Response:
    return Response(
        json.dumps({"input_errors": errors}, indent=2),
        mimetype="application/json",
        status=status,
    )


def _merge_args(document: dict) -> None:
    if not hasattr(g, "args") or g.args is None:
        g.args = {}
    g.args.update(document)


def parse_json_body():
    """Parse the request body with dustmaps' decoder; returns (payload, error)."""
    raw = request.get_data(cache=True)
    if not raw:
        return None, _error_response({"body": ["Request body is empty; expected JSON."]})
    try:
        payload = json.loads(raw, cls=json_serializers.MultiJSONDecoder)
    except Exception as err:
        return None, _error_response({"body": [f"Could not parse JSON: {err}"]})
    if not isinstance(payload, dict):
        return None, _error_response({"body": ["Expected a JSON object."]})
    return payload, None


def validate_json(*schemata, **kw):
    v = get_validator(*schemata, **kw)

    def decorator(f):
        @functools.wraps(f)
        def validated(*args, **kwargs):
            payload, error = parse_json_body()
            if error is not None:
                return error
            if not v.validate(payload):
                return _error_response(v.errors)
            _merge_args(v.document)
            return f(*args, **kwargs)

        return validated

    return decorator


def validate_qstring(*schemata, **kw):
    v = get_validator(*schemata, **kw)

    def decorator(f):
        @functools.wraps(f)
        def validated(*args, **kwargs):
            if not v.validate(request.args.to_dict()):
                return _error_response(v.errors)
            _merge_args(v.document)
            return f(*args, **kwargs)

        return validated

    return decorator


def skycoords_from_args():
    def decorator(f):
        @functools.wraps(f)
        def with_skycoords(*args, **kwargs):
            if "coords" in g.args:
                coords = g.args.pop("coords")
            elif "l" in g.args:
                coords = SkyCoord(
                    g.args.pop("l"),
                    g.args.pop("b"),
                    distance=g.args.pop("d", None),
                    frame="galactic",
                )
            elif "ra" in g.args:
                coords = SkyCoord(
                    g.args.pop("ra"),
                    g.args.pop("dec"),
                    distance=g.args.pop("d", None),
                    frame=g.args.pop("frame", "icrs"),
                )
            elif "lon" in g.args:
                coords = SkyCoord(
                    g.args.pop("lon"),
                    g.args.pop("lat"),
                    frame={"gal": "galactic", "equ": "icrs"}.get(
                        g.args.pop("coordsys")
                    ),
                )
            else:
                return _error_response(
                    {"coords": ["No coordinate specification in input."]}
                )

            g.n_coords = 1 if coords.isscalar else int(np.size(coords))
            return f(coords, *args, **kwargs)

        return with_skycoords

    return decorator
