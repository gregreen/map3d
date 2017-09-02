from __future__ import print_function, division

from map3d import mapdata

import numpy as np
np.seterr(invalid='ignore')

import healpy as hp

import itertools

import os
import urllib
from PIL import Image
from cStringIO import StringIO

import hputils
import proj_fast

script_dir = os.path.dirname(os.path.realpath(__file__))
media_path = os.path.join(script_dir, 'static', 'media')

# Pre-generate rasterizer
img_shape = (500, 500)
radius = 1.5*7.5
rasterizer = proj_fast.MapRasterizerFast(
    mapdata.image_data['bayestar2015'][0],
    img_shape,
    fov=2*radius)


import time

def encode_image(img_arr, c_mask=(202,222,219)):
    t3 = time.time()

    # Generate 8-bit grayscale image
    img_arr = img_arr.T[::-1,:]
    nan_mask = ~np.isfinite(img_arr)

    img_arr[img_arr > 1.] = 1.

    img_arr = (255. * img_arr).astype(np.uint8)
    # img_arr[nan_mask] = 255

    # Convert to color image with mask color
    if np.any(nan_mask):
        img_arr_color = np.empty(img_arr.shape+(3,), dtype=np.uint8)
        for k in range(3):
            img_arr_color[:,:,k] = img_arr[:,:]
            img_arr_color[nan_mask,k] = c_mask[k]
        img = Image.fromarray(img_arr_color, mode='RGB')
    else:
        img = Image.fromarray(img_arr, mode='L')

    t4 = time.time()

    img_io = StringIO()
    # img.save(img_io, 'PNG', transparency=255, compress_level=2)
    img.save(img_io, 'JPEG', quality=40)
    img_io.seek(0)

    t5 = time.time()

    data = img_io.getvalue().encode('base64')
    data = 'data:image/jpg;base64,{0}'.format(urllib.quote(data.rstrip('\n')))

    t6 = time.time()

    print('')
    print('prepare: {:.4f} s'.format(t4-t3))
    print('save: %.4f s' % (t5-t4))
    print('encode: %.4f s' % (t6-t5))
    print('total: %.4f s' % (t6-t4))
    print('size: %.2f kB' % (len(data) / 1024.))
    print('')

    return data


def postage_stamps(map_name, l, b,
                   dists=[300., 1000., 5000.],
                   difference=False):
    t1 = time.time()
    map_nside, map_pixval = mapdata.image_data[map_name]
    pix_val = [map_pixval[:,k] for k in xrange(len(dists))]
    t2 = time.time()
    img = rasterizer.rasterize(pix_val, l, b)
    t3 = time.time()

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

    t4 = time.time()

    print('pix_val: {:.4f} s'.format(t2-t1))
    print('rasterize: {:.4f} s'.format(t3-t2))
    print('normalize: {:.4f} s'.format(t4-t3))

    return img
