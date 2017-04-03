from __future__ import print_function, division

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as units
from map3d import mapdata


def is_array_or_scalar_type(d):
    if isinstance(d, float) or isinstance(d, int):
        return True
    if isinstance(d, list):
        for el in d:
            if (not isinstance(el, float)) and (not isinstance(el, int)):
                return False
        return True
    if isinstance(d, np.ndarray):
        np_dtypes = (
            np.dtype('float64'),
            np.dtype('float32'),
            np.dtype('float16'),
            np.dtype('int32'),
            np.dtype('int64')
        )
        if d.dtype in np_dtypes:
            return True
    return False

def parse_coords_kwargs(json_data, coord_format='query', n_coords_max=None):
    def check_n_coords(n):
        if n_coords_max is None:
            return None
        if n > n_coords_max:
            msg = 'Too many coordinates requested (requested: {:d}, max: {:d})'.format(
                n_coords, n_coords_max)
            return None, None, None, (msg, 413)

    if not isinstance(json_data, dict):
        return 'JSON data included in request must be a dictionary.', 400

    if coord_format == 'query':
        # Standard astropy.SkyCoord request
        if 'coords' not in json_data:
            msg = 'Require "coords" in request.'
            return None, None, None, (msg, 400)

        coords = json_data.pop('coords')

        if not isinstance(coords, SkyCoord):
            return '"coords" must be an astropy.SkyCoord object.'

        if coords.isscalar:
            n_coords = 1
        else:
            n_coords = len(coords)
        check = check_n_coords(n_coords)
        if check is not None:
            return check

        return coords, json_data, None
    elif coord_format == 'query_gal':
        # query_gal request
        keys = ['l', 'b']
    elif coord_format == 'query_equ':
        # query_equ request
        keys = ['ra', 'dec']
    else:
        raise ValueError('Invalid "coord_format": {}'.format(coord_format))

    # Validate query_gal and query_equ requests
    coords = {}
    n_coords = None

    def get_len_safe(x):
        if isinstance(x, units.Quantity):
            if x.isscalar:
                return 1
        if hasattr(x, '__len__'):
            return len(x)
        return 1

    for k in keys:
        if k not in json_data:
            msg = 'Require "{:s}" in request.'.format(k)
            return None, None, None, (msg, 400)

        coords[k] = json_data.pop(k)

        if n_coords is None:
            n_coords = get_len_safe(coords[k])
            check = check_n_coords(n_coords)
            if check is not None:
                return check
        elif get_len_safe(coords[k]) != n_coords:
            msg = '{} must be the same length'.format(keys)
            return None, None, None, (msg, 400)

        if not is_array_or_scalar_type(coords[k]):
            msg = '"{:s}" must be either a float or array of floats.'.format(k)
            return None, None, None, (msg, 400)

    return n_coords, coords, json_data, None


handlers = {
    'bayestar2015': (mapdata.bayestar2015, None)
    # 'sfd': (mapdata.sfd, None),
    # 'planck': (mapdata.planck, None),
    # 'marshall': (mapdata.marshall, None)
}
