import numpy as np
np.seterr(invalid='ignore')

import healpy as hp

import itertools

import urllib
from PIL import Image
from StringIO import StringIO

import hputils


def encode_image(img_arr, c_mask=(202,222,219)):
    img_arr = img_arr.T[::-1,:]
    nan_mask = ~np.isfinite(img_arr)
    
    img_arr[img_arr > 1.] = 1.
    
    img_arr = (255. * img_arr).astype(np.uint8)
    img_arr.shape = (img_arr.shape[0], img_arr.shape[1], 1)
    img_arr = np.repeat(img_arr, 3, axis=2)
    
    for k in xrange(3):
        img_arr[nan_mask, k] = c_mask[k]
    
    img = Image.fromarray(img_arr, mode='RGB')
    
    img_io = StringIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    data = img_io.getvalue().encode('base64')
    data = 'data:image/png;base64,{0}'.format(urllib.quote(data.rstrip('\n')))
    
    return data


def postage_stamps(map_pixval, map_nside, l, b,
                   radius=15., width=500,
                   dists=[300., 1000., 5000.],
                   difference=False):
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
    
    if difference:
        img[2] -= img[1]
        img[1] -= img[0]
        
        idx = np.isfinite(img)
        
        if np.sum(idx) == 0:
            return img
        
        vmax = np.percentile(img[idx], 99.5)
    else:
        idx = np.isfinite(img[-1])
        
        if np.sum(idx) == 0:
            return img
        
        vmax = np.percentile(img[-1][idx], 99.)
    
    for i in img:
        i *= 1./vmax
    
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
