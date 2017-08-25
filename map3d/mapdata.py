from __future__ import print_function, division

import os
import h5py
import numpy as np

from dustmaps.sfd import SFDQuery
from dustmaps.bayestar import BayestarQuery
from dustmaps.planck import PlanckQuery
from dustmaps.marshall import MarshallQuery

import validators


script_dir = os.path.dirname(os.path.realpath(__file__))
data_path = os.path.join(script_dir, 'static', 'data')


def load_images():
    slice_idx = [7, 12, 19]

    fname = os.path.join(data_path, 'EBV_1024_f4.h5')
    with h5py.File(fname, 'r') as f:
        nside = f['EBV'].attrs['nside']
        EBV_slices = f['EBV'][slice_idx,:]

    EBV_slices[EBV_slices == 0.] = np.nan

    return nside, EBV_slices.T


print('Loading Bayestar2015 ...')
bayestar2015 = BayestarQuery(
    map_fname=os.path.join(data_path, 'dust-map-3d.h5'),
    max_samples=10)
print('Loading SFD ...')
sfd = SFDQuery(map_dir=data_path)
# planck = PlanckQuery()
# marshall = MarshallQuery()
print('Loading map images ...')
map_nside, map_pixval = load_images()
print('Done loading data.')


#
# Validate keyword arguments to individual dust maps
#

bayestar_schema = {
    'mode': {
        'type': 'string',
        'anyof': [
            {
                'allowed': [
                    'random_sample',
                    'random_sample_per_pix',
                    'samples',
                    'median',
                    'mean',
                    'best'
                ]
            },
            {
                'allowed': ['percentile'],
                'dependencies': 'pct'
            }
        ]
    },
    'pct': {
        'coerce': validators.to_array('f8'),
        'type': 'numberlike_ndarray',
        'minall': 0.,
        'maxall': 100.,
        'dependencies': {'mode': 'percentile'},
        'nullable': True
    },
    'return_flags': {
        'type': 'boolean'
    }
}

sfd_schema = {
    'order': {
        'type': 'integer',
        'min': 0,
        'max': 5
    }
}

def bayestar_query_size_calculator(q_obj):
    def bayestar_query_size(coords, mode='random_sample', pct=None, return_flags=False):
        # pct, scalar_pct = q_obj._interpret_percentile(mode, pct)

        n_coords = coords.size #np.prod(coords.shape, dtype=int)

        if mode == 'samples':
            n_samples = q_obj._n_samples
        elif mode == 'percentile':
            n_samples = np.array(pct).size
        else:
            n_samples = 1

        if hasattr(coords.distance, 'kpc'):
            n_dists = 1
        else:
            n_dists = q_obj._n_distances

        return n_coords * n_samples * n_dists
    return bayestar_query_size


def default_query_size(coords, **kwargs):
    return coords.size


def get_size_checker(max_size, f_size=default_query_size):
    def fn(coords, **kwargs):
        s = f_size(coords, **kwargs)
        if s > max_size:
            return False, s, max_size
        return True, None, None
    return fn


# Dictionary indexing the different maps by name.
# Each entry must include the query object, and may include a validation schema
# for the keyword arguments, and a size checker that determines whether or not
# the requested output is too large.
handlers = {
    'bayestar2015': {
        'q': bayestar2015,
        'schema': bayestar_schema,
        'size_checker': get_size_checker(
            1.e6,
            f_size=bayestar_query_size_calculator(bayestar2015))
    },
    'sfd': {
        'q': sfd,
        'schema': sfd_schema,
        'size_checker': get_size_checker(1.e6)
    }
    # 'planck': (mapdata.planck, None),
    # 'marshall': (mapdata.marshall, None)
}
