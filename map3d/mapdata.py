
import os
import h5py
import numpy as np


script_dir = os.path.dirname(os.path.realpath(__file__))
static_path = os.path.join(script_dir, 'static')


def load_images():
    slice_idx = [7, 12, 19]
    
    print 'Loading map ...'
    
    fname = os.path.join(static_path, 'EBV_1024_f4.h5')
    f = h5py.File(fname, 'r')
    nside = f['EBV'].attrs['nside']
    EBV_slices = f['EBV'][slice_idx,:]
    f.close()
    
    EBV_slices[EBV_slices == 0.] = np.nan
    
    print 'Done loading.'
    
    return nside, EBV_slices.T


map_nside, map_pixval = load_images()

mapper = None
