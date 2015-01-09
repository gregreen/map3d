import numpy as np
import healpy as hp
import h5py

import itertools
import os

import urllib
from PIL import Image
from StringIO import StringIO

import hputils


script_dir = os.path.dirname(os.path.realpath(__file__))
static_path = os.path.join(script_dir, 'static')


def load_data():
    slice_idx = [7, 12, 19]
    
    print 'Loading map ...'
    
    fname = os.path.join(static_path, 'EBV_1024_f4.h5')
    f = h5py.File(fname, 'r')
    nside = f['EBV'].attrs['nside']
    EBV_slices = f['EBV'][slice_idx,:]
    f.close()
    
    print 'Done loading.'
    
    return nside, EBV_slices.T
    
    '''
    nside = 512
    radius = 5.
    l, b = 30., 15.
    
    print 'Generating map...'
    n_pix = hp.pixelfunc.nside2npix(nside)
    
    t_0 = np.radians(90. - b)
    p_0 = np.radians(l)
    
    theta, phi = hp.pixelfunc.pix2ang(nside, np.arange(n_pix), nest=True)
    dist = hp.rotator.angdist([t_0, p_0], [theta, phi])
    
    m = np.sinc(3.5 * dist/np.radians(radius))
    m = np.sqrt(np.abs(m))
    m /= np.max(m)
    print m
    
    return nside, np.array([m/3., m*2./3., m]).T
    '''


def encode_image(img_arr):
    img_arr = (255. * img_arr.T[::-1,:]).astype(np.uint8)
    img = Image.fromarray(img_arr, mode='L')
    
    img_io = StringIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    data = img_io.getvalue().encode('base64')
    data = 'data:image/png;base64,{0}'.format(urllib.quote(data.rstrip('\n')))
    
    return data


def postage_stamps(l, b, radius=15., width=500, dists=[300., 1000., 5000.]):
    img_shape = (2*width, 2*width)
    
    x0 = width/2
    x1 = -width/2
    y0 = width/2
    y1 = -width/2
    
    pix_idx = grab_region(map_nside, l, b, radius=radius)
    nside = map_nside * np.ones(pix_idx.size, dtype='i8')
    
    proj = hputils.Gnomonic_projection()
    rasterizer = hputils.MapRasterizer(nside, pix_idx, img_shape,
                                       nest=True, clip=True,
                                       proj=proj, l_cent=l, b_cent=b)
    
    pix_val = map_pixval[pix_idx]
    
    img = [rasterizer(pix_val[:,k])[x0:x1, y0:y1] for k,d in enumerate(dists)]
    
    vmax = np.percentile(img[-1], 99.)
    
    for i in img:
        i *= 1./vmax
        i[i > 1.] = 1.
    
    return img


def grab_region(nside, l, b, radius=1.):
    i_0 = hputils.lb2pix(nside, l, b)
    vec_0 = hp.pixelfunc.pix2vec(nside, i_0, nest=True)
    
    ipix = hp.query_disc(nside, vec_0, np.radians(radius), True, 2, True)
    
    return ipix


def rasterize_region(m, l, b, radius=1.,
                              proj=hputils.Gnomonic_projection(),
                              img_shape=(250,250)):
    nside = hp.pixelfunc.npix2nside(m.size)
    pix_idx = grab_region(nside, l, b, radius=radius)
    nside = nside * np.ones(pix_idx.size, dtype='i8')
    
    rasterizer = hputils.MapRasterizer(nside, pix_idx, img_shape,
                                       nest=True, clip=True,
                                       proj=proj, l_cent=l, b_cent=b)
    
    img = rasterizer(m[pix_idx])
    
    return img


map_nside, map_pixval = load_data()
