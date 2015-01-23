#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  proj_fast.py
#  
#  Copyright 2015 greg <greg@greg-UX301LAA>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import numpy as np
import healpy as hp

from hputils import Euler_rotation_ang, Gnomonic_projection, lb2pix, pix2lb


class MapRasterizerFast:
    '''
    A class that rasterizes single-resolution HEALPix maps.
    
    Pre-computes mapping between display-space pixels and HEALPix
    pixels, so that maps with different pixel intensities can be
    rasterized quickly.
    '''
    
    def __init__(self, nside, img_shape,
                       fov=10., nest=True,
                       proj=Gnomonic_projection()):
        self.img_shape = img_shape
        self.proj = proj
        self.nside = nside
        self.nest = nest
        
        # Determine maximum x- and y-coordinates to get desired field of
        # view
        l = np.radians(np.array([-0.5*fov, 0.5*fov, 0., 0.]))
        b = np.radians(np.array([0., 0., -0.5*fov, 0.5*fov]))
        x, y = proj.proj(b, l)
        x_min, x_max = x[:2]
        y_max, y_min = y[2:]
        
        # Create a grid of projected coordinates (e.g., display space)
        x_size, y_size = img_shape
        
        x, y = np.mgrid[0:x_size, 0:y_size].astype(np.float32) + 0.5
        x = ( x_min + (x_max - x_min) * x / float(x_size) ).flatten()
        y = ( y_min + (y_max - y_min) * y / float(y_size) ).flatten()
        
        # Invert projection to get coordinates on sphere (l, b)
        b, lam, self.clip_mask = proj.inv(x, y)
        l = 180. - 180./np.pi * lam
        b *= 180./np.pi
        del lam
        
        self.l_0 = l
        self.b_0 = b
    
    def _get_pix_index(self, l_cent, b_cent):
        l, b = self.l_0, self.b_0
        
        # Rotate back to original (l, b)-space
        if (l_cent != 0.) | (b_cent != 0.):
            b, l = Euler_rotation_ang(self.b_0, self.l_0,
                                      -l_cent, b_cent, 0.,
                                      degrees=True, inverse=True)
        
        # Map (l,b) to HEALPix index
        return lb2pix(self.nside, l, b, nest=self.nest)
    
    def rasterize(self, map_list, l_cent, b_cent):
        hp_idx = self._get_pix_index(l_cent, b_cent)
        
        '''
        np.set_printoptions(precision=2, linewidth=140)
        print np.reshape(hp_idx, self.img_shape)
        l, b = pix2lb(self.nside, hp_idx)
        print np.reshape(l, self.img_shape).T
        print np.reshape(b, self.img_shape).T
        print np.reshape(map_list[0][hp_idx], self.img_shape).T
        '''
        
        shape = (len(map_list), self.img_shape[0] * self.img_shape[1])
        img_stack = np.zeros(shape, dtype=map_list[0].dtype)
        
        for k,m in enumerate(map_list):
            img_stack[k][:] = m[hp_idx]
        
        img_stack.shape = (len(map_list), self.img_shape[0], self.img_shape[1])
        
        return img_stack


'''
def test_proj():
    import matplotlib.pyplot as plt
    import time
    
    from postage_stamp import postage_stamps
    
    nside = 256
    l_0, b_0 = (45, 0)
    fov = 15
    img_width = 500
    
    img_shape = (img_width, img_width)
    
    n_pix = hp.nside2npix(nside)
    pix_idx = np.arange(n_pix)
    l, b = pix2lb(nside, pix_idx)
    pix_val = np.sin(l/3.) * np.cos(b/5.) * (l-l_0)**2. * (b-b_0)**2. #np.arange(n_pix)
    
    # Set up figure
    fig = plt.figure(figsize=(10,5), dpi=150)
    
    # Rasterize the old way
    #pix_idx = np.arange(n_pix)
    #nside_arr = nside * np.ones(pix_idx.size, dtype='i4')
    
    map_pixval = np.vstack([pix_val, pix_val, pix_val]).T
    
    t_0 = time.time()
    #rasterizer = hputils.MapRasterizer(nside_arr, pix_idx, (500,500),
    #                                   l_cent=l_0, b_cent=b_0,
    #                                   nest=nest)
    #img = rasterizer(pix_val)
    img_stack = postage_stamps(map_pixval, nside, l_0, b_0,
                               radius=0.5*fov, width=img_width,
                               dists=[300.],
                               difference=False)
    t_1 = time.time()
    
    print 'Time to rasterize map 1'
    
    bounds = [-0.5*fov, 0.5*fov, -0.5*fov, 0.5*fov]
    vmin = np.min(img_stack[0])
    vmax = np.max(img_stack[0])
    
    print 'v_min:', vmin
    print 'v_max:', vmax
    
    ax = fig.add_subplot(1,2,1)
    cimg = ax.imshow(img_stack[0].T, extent=bounds,
                     origin='lower', interpolation='nearest',
                     aspect='equal', vmin=vmin, vmax=vmax)
    
    # Rasterize the new way
    t_2 = time.time()
    rasterizer = MapRasterizerFast(nside, img_shape, fov=fov)
    t_3 = time.time()
    img_stack = rasterizer.rasterize([pix_val, pix_val, pix_val], l_0, b_0)
    norm = np.percentile(img_stack[-1], 99.)
    img_stack /= norm
    t_4 = time.time()
    
    ax = fig.add_subplot(1,2,2)
    cimg = ax.imshow(img_stack[0].T, extent=bounds,
                     origin='lower', interpolation='nearest',
                     aspect='equal', vmin=vmin, vmax=vmax)
    
    print 'Old postage stamp: %.3f' % (t_1 - t_0)
    print 'New postage stamp pre-compute: %.3f' % (t_3 - t_2)
    print 'New postage stamp: %.3f' % (t_4 - t_3)
    
    plt.show()


def main():
    test_proj()
    
    return 0

if __name__ == '__main__':
    main()
'''
