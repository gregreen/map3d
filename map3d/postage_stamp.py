import numpy as np
np.seterr(invalid='ignore')

import healpy as hp

import itertools

import os
import urllib
from PIL import Image
from StringIO import StringIO

import hputils
import proj_fast

script_dir = os.path.dirname(os.path.realpath(__file__))
media_path = os.path.join(script_dir, 'static', 'media')


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
                   radius=7.5, width=500,
                   dists=[300., 1000., 5000.],
                   difference=False):
    img_shape = (width, width)
    rasterizer = proj_fast.MapRasterizerFast(map_nside, img_shape, fov=2*radius)
    pix_val = [map_pixval[:,k] for k in xrange(len(dists))]
    img = rasterizer.rasterize(pix_val, l, b)
    
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


def encode_imgfile(fname):
    f = open(os.path.join(media_path, fname), 'r')
    data = f.read().encode('base64')
    f.close()
    
    data = 'data:image/png;base64,{0}'.format(urllib.quote(data.rstrip('\n')))
    
    return data
