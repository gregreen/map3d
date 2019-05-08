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


def gen_images(q, nside, dists, **kwargs):
    import healpy as hp
    n_pix = hp.pixelfunc.nside2npix(nside)
    l,b = hp.pixelfunc.pix2ang(nside, np.arange(n_pix),
                               lonlat=True, nest=True)
    img = np.vstack([q.query_gal(l, b, d=d, **kwargs) for d in dists])
    return nside, img.T


print('Loading Bayestar2015 ...')
bayestar2015 = BayestarQuery(
    map_fname=os.path.join(data_path, 'bayestar2015.h5'),
    max_samples=5)
print('Loading Bayestar2017 ...')
bayestar2017 = BayestarQuery(
    map_fname=os.path.join(data_path, 'bayestar2017.h5'),
    max_samples=5)
print('Loading Bayestar2019 ...')
bayestar2019 = BayestarQuery(
    map_fname=os.path.join(data_path, 'bayestar2019.h5'),
    max_samples=5)
print('Loading SFD ...')
sfd = SFDQuery(map_dir=data_path)
# planck = PlanckQuery()
# marshall = MarshallQuery()
print('Generating map images ...')
image_data = {
    'bayestar'+n: gen_images(q, 1024, (0.3, 1., 5.), mode='mean')
    for n,q in (('2015',bayestar2015),('2017',bayestar2017),('2019',bayestar2019))
}
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
    'bayestar2017': {
        'q': bayestar2017,
        'schema': bayestar_schema,
        'size_checker': get_size_checker(
            1.e6,
            f_size=bayestar_query_size_calculator(bayestar2017))
    },
    'bayestar2019': {
        'q': bayestar2019,
        'schema': bayestar_schema,
        'size_checker': get_size_checker(
            1.e6,
            f_size=bayestar_query_size_calculator(bayestar2019))
    },
    'sfd': {
        'q': sfd,
        'schema': sfd_schema,
        'size_checker': get_size_checker(1.e6)
    }
    # 'planck': (mapdata.planck, None),
    # 'marshall': (mapdata.marshall, None)
}
