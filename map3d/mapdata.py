from __future__ import print_function, division

import os
import h5py
import numpy as np

from dustmaps.sfd import SFDQuery
from dustmaps.bayestar import BayestarQuery
from dustmaps.planck import PlanckQuery
from dustmaps.marshall import MarshallQuery


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


# Dictionary indexing the different maps by name
# Format: (query_object, max # of coords per query)
handlers = {
    'bayestar2015': (bayestar2015, None),
    'sfd': (sfd, None),
    # 'planck': (mapdata.planck, None),
    # 'marshall': (mapdata.marshall, None)
}
