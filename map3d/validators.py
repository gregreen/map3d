from __future__ import print_function, division

from werkzeug.exceptions import BadRequest

from flask import g, request, Response
import flask

from cerberus import Validator
from cerberus.platform import _int_types, _str_type

import ujson as json
import functools

import numpy as np
import astropy.units as units
from astropy.coordinates import SkyCoord
from astropy.units import Quantity


class ExtendedValidator(Validator):
    def __init__(self, *args, **kwargs):
        # if 'additional_context' in kwargs:
        #     self.additional_context = kwargs['additional_context']
        super(ExtendedValidator, self).__init__(*args, **kwargs)

    def _validate_type_skycoord(self, value):
        return isinstance(value, SkyCoord)

    def _validate_type_numberlike_ndarray(self, value):
        if isinstance(value, np.ndarray):
            return (value.dtype.kind in 'iuf')
        return False

    def _validate_type_quantity(self, value):
        return isinstance(value, Quantity)

    def _validate_type_angle(self, value):
        return (isinstance(value, Quantity) and value.unit.is_equivalent(units.rad))

    def _validate_type_length(self, value):
        return (isinstance(value, Quantity) and value.unit.is_equivalent(units.m))

    def _validate_type_scalar(self, value):
        if type in (float, int, np.floating, np.integer):
            return True
        elif isinstance(value, Quantity) and value.isscalar:
            return True
        return False

    def _validate_type_list_of_numbers(self, value):
        if type(value) not in (list, tuple):
            return False
        for el in value:
            if type(el) not in (float, int, long):
                return False
        return True

    def _validate_type_np_number(self, value):
        return (isinstance(value, np.floating) or isinstance(value, np.integer))

    def _validate_maxall(self, max_val, field, value):
        """
        Test whether all the elements of an array are greater than a given
        amount.

        The rule's arguments are validated against this schema:
        {}
        """
        if np.any(value > max_val):
            self._error(field, 'Must not be greater than {}'.format(max_val))

    def _validate_minall(self, min_val, field, value):
        """
        Test whether all the elements of an array are less than a given amount.

        The rule's arguments are validated against this schema:
        {}
        """
        if np.any(value < min_val):
            self._error(field, 'Must not be less than {}'.format(min_val))

    def _validate_sameshape(self, target_field, field, value):
        """
        Test whether this field has the same shape as one or more other fields.
        If a target field does not exist, no error is raised (use 'dependency'
        to require the existence of the target field).

        The rule's arguments are validated against this schema:
        {'type': ['string', 'list']}
        """
        if isinstance(target_field, _str_type):
            target_field = [target_field]
        shape = value.shape
        for target in target_field:
            res = self._lookup_field(target)[1]
            if res is None:
                return True # Target field does not exist
                # self._error(field, 'Must have same shape as {}, which is not present.'.format(target))
            elif not hasattr(res, 'shape'):
                self._error(field, 'Must have same shape as {}, which has no shape.'.format(target))
            elif res.shape != shape:
                self._error(field, 'Must have same shape as {}.'.format(target))
        return True


def to_array(dtype):
    def f(value):
        return np.array(value, dtype=dtype)
    return f


def to_quantity(unit_spec, dtype='f8'):
    def f(value):
        if value is None:
            return None
        if isinstance(value, Quantity):
            return value.to(unit_spec)
        elif isinstance(value, np.ndarray):
            return value.astype(dtype) * unit_spec
        else:
            return np.array(value, dtype=dtype) * unit_spec
    return f


common_validators = {
    'skycoord': {
        'coords': {
            'type': 'skycoord',
            'excludes': ['l', 'b', 'ra', 'dec', 'd']},
    },
    'gal': {
        'l': {
            'coerce': to_quantity(units.deg),
            'type': 'angle',
            'excludes': ['coords', 'ra', 'dec'],
            'dependencies': 'b',
            'sameshape': 'b'},
        'b': {
            'coerce': to_quantity(units.deg),
            'type': 'angle',
            'maxall': 90.*units.deg,
            'minall': -90.*units.deg,
            'excludes': ['coords', 'ra', 'dec'],
            'dependencies': 'l'},
    },
    'equ': {
        'ra': {
            'coerce': to_quantity(units.deg),
            'type': 'angle',
            'excludes': ['coords', 'l', 'b'],
            'dependencies': 'dec',
            'sameshape': 'dec'},
        'dec': {
            'coerce': to_quantity(units.deg),
            'type': 'angle',
            'maxall': 90.*units.deg,
            'minall': -90.*units.deg,
            'excludes': ['coords', 'l', 'b'],
            'dependencies': 'ra'},
    },
    'distance': {
        'd': {
            'required': False,
            'coerce': to_quantity(units.kpc),
            'type': 'length',
            'excludes': 'coords',
            'minall': 0.*units.kpc,
            'nullable': True,
            'anyof': [
                {'sameshape': 'l'},
                {'sameshape': 'ra'},
                {'type': 'scalar'}
            ]
        }
    },
    'mode-legacy': {
        'mode': {
            'required': False,
            'type': 'string',
            'allowed': ['full', 'lite', 'sfd'],
            'default': 'full'
        }
    },
    'equ-frame': {
        'frame': {
            'required': False,
            'type': 'string',
            'allowed': ['icrs', 'fk5', 'fk4', 'fk4noeterms'],
            'excludes': ['coords', 'l', 'b']
        }
    },
    'scalar-lonlat': {
        'lon': {
            'required': True,
            'coerce': to_quantity(units.deg),
            'allof': [
                {'type': 'scalar'},
                {'type': 'angle'}]},
        'lat': {
            'required': True,
            'coerce': to_quantity(units.deg),
            'allof': [
                {'type': 'scalar'},
                {'type': 'angle'}],
            'min': -90.*units.deg,
            'max': 90.*units.deg},
        'coordsys': {
            'required': True,
            'type': 'string',
            'allowed': ['gal', 'equ']}
    }
}


def get_validator(*args, **kwargs):
    """
    Returns a validator that combines one or more of the schemata in
    ``common_validators``.

    Args:
        *args: The names of the schemata (e.g., 'gal', 'equ').
        **kwargs: Additional arguments to pass on to the
    """
    schema = {}
    for a in args:
        schema.update(common_validators[a])
    return ExtendedValidator(schema, **kwargs)


def validate_json(*schemata, **kw):
    v = get_validator(*schemata, **kw)

    def json_parse_error(e):
        raise BadRequest(description=str(e))

    def decorator(f):
        @functools.wraps(f)
        def validated(*args, **kwargs):
            # Monkey-patch request to return more descriptive error message
            # if JSON parsing fails
            request.on_json_loading_failed = json_parse_error

            # print('validating...')
            if not v.validate(request.json):
                return Response(
                    json.dumps({'input_errors': v.errors}, indent=2),
                    mimetype='application/json',
                    status=400)

            if not hasattr(g, 'args'):
                g.args = {}
            g.args.update(v.document)

            return f(*args, **kwargs)
        return validated

    return decorator


def validate_qstring(*schemata, **kw):
    v = get_validator(*schemata, **kw)

    def json_parse_error(e):
        raise BadRequest(description=str(e))

    def decorator(f):
        @functools.wraps(f)
        def validated(*args, **kwargs):
            # print('validating query string...')
            if not v.validate(request.args.to_dict()):
                return Response(
                    json.dumps({'input_errors': v.errors}, indent=2),
                    mimetype='application/json',
                    status=400)

            if not hasattr(g, 'args'):
                g.args = {}
            g.args.update(v.document)

            return f(*args, **kwargs)
        return validated

    return decorator


def skycoords_from_args():
    def decorator(f):
        @functools.wraps(f)
        def with_skycoords(*args, **kwargs):
            # print('getting skycoords...')

            if 'coords' in g.args:
                coords = g.args.pop('coords')
            elif 'l' in g.args:
                coords = SkyCoord(
                    g.args.pop('l'),
                    g.args.pop('b'),
                    distance=g.args.pop('d', None),
                    frame='galactic')
            elif 'ra' in g.args:
                coords = SkyCoord(
                    g.args.pop('ra'),
                    g.args.pop('dec'),
                    distance=g.args.pop('d', None),
                    frame=g.args.pop('frame', 'icrs'))
            elif 'lon' in g.args:
                coords = SkyCoord(
                    g.args.pop('lon'),
                    g.args.pop('lat'),
                    frame={'gal':'galactic', 'equ':'icrs'}.get(
                        g.args.pop('coordsys')))
            else:
                return 'No coordinate specifications in input.', 400

            if coords.isscalar:
                g.n_coords = 1
            else:
                g.n_coords = len(coords)

            return f(coords, *args, **kwargs)
        return with_skycoords
    return decorator

def get_n_coords():
    def decorator(f):
        @functools.wraps(f)
        def with_n_coords(*args, **kwargs):
            for key in ['coords', 'l', 'ra', 'lon']:
                if key in g.args:
                    try:
                        g.n_coords = len(g.args[key])
                    except AttributeError as err:
                        g.n_coords = 1
                    break
            return f(*args, **kwargs)
        return with_n_coords
    return decorator
