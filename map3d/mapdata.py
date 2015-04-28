
import os
import h5py
import numpy as np

import astropy.wcs as pywcs
import astropy.io.fits as pyfits
from scipy.ndimage import map_coordinates

import hputils

from utils import array_like

script_dir = os.path.dirname(os.path.realpath(__file__))
data_path = os.path.join(script_dir, 'static', 'data')


def load_images():
    slice_idx = [7, 12, 19]
    
    fname = os.path.join(data_path, 'EBV_1024_f4.h5')
    f = h5py.File(fname, 'r')
    nside = f['EBV'].attrs['nside']
    EBV_slices = f['EBV'][slice_idx,:]
    f.close()
    
    EBV_slices[EBV_slices == 0.] = np.nan
    
    return nside, EBV_slices.T


class MapQuery:
    def __init__(self, fname):
        f = h5py.File(fname, 'r')
        
        # Load pixel information
        self.pixel_info = f['/pixel_info'][:]
        
        # Load reddening, GR diagnostic
        self.samples = f['/samples'][:]
        self.best_fit = f['/best_fit'][:]
        self.GR = f['/GRDiagnostic'][:]
        
        f.close()
        
        # Get healpix indices at each nside level
        sort_idx = np.argsort(self.pixel_info, order=['nside', 'healpix_index'])
        
        self.nside_levels = np.unique(self.pixel_info['nside'])
        self.hp_idx_sorted = []
        self.data_idx = []
        
        start_idx = 0
        
        for nside in self.nside_levels:
            end_idx = np.searchsorted(self.pixel_info['nside'], nside,
                                      side='right', sorter=sort_idx)
            
            idx = sort_idx[start_idx:end_idx]
            
            self.hp_idx_sorted.append(self.pixel_info['healpix_index'][idx])
            self.data_idx.append(idx)
            
            start_idx = end_idx
    
    def _find_data_idx(self, l, b):
        pix_idx = np.empty(l.shape, dtype='i8')
        pix_idx[:] = -1
        
        # Search at each nside
        for k,nside in enumerate(self.nside_levels):
            ipix = hputils.lb2pix(nside, l, b, nest=True)
            
            # Find the insertion points of the query pixels in the large, ordered pixel list
            idx = np.searchsorted(self.hp_idx_sorted[k], ipix, side='left')
            
            # Determine which insertion points are beyond the edge of the pixel list
            in_bounds = (idx < self.hp_idx_sorted[k].size)
            
            if not np.any(in_bounds):
                continue
            
            # Determine which query pixels are correctly placed
            idx[~in_bounds] = -1
            match_idx = (self.hp_idx_sorted[k][idx] == ipix)
            match_idx[~in_bounds] = False
            idx = idx[match_idx]
            
            if np.any(match_idx):
                pix_idx[match_idx] = self.data_idx[k][idx]
        
        return pix_idx
    
    def query(self, l, b, mode='full'):
        # Ensure that l and b are arrays
        is_scalar = False
        
        if not array_like(l):
            is_scalar = True
            l = np.array([l])
            b = np.array([b])
        
        idx = self._find_data_idx(l, b)
        
        pix_info = self.pixel_info[idx]
        
        ret = {}
        ret['samples'] = self.samples[idx]
        ret['best'] = self.best_fit[idx]
        ret['GR'] = self.GR[idx]
        ret['n_stars'] = pix_info['n_stars']
        ret['DM_reliable_min'] = pix_info['DM_reliable_min']
        ret['DM_reliable_max'] = pix_info['DM_reliable_max']
        ret['converged'] = pix_info['converged']
        
        if mode == 'lite':
            ret['samples'] = ret['samples'][:,:5]
            x_low, x_med, x_high = np.percentile(ret['samples'], [15.8, 50., 84.2], axis=1)
            sigma = 0.5*(x_high - x_low)
            sigma = np.sqrt(sigma**2 + 0.03**2)
            ret['median'] = x_med
            ret['sigma'] = sigma
            ret.pop('samples')
            ret.pop('GR')
        elif mode != 'full':
            raise ValueError('Unknown query mode passed to MapQuery.query: {}'.format(mode))
        
        idx_null = (idx == -1)
        
        if np.any(idx_null):
            for key in ret.keys():
                ret[key][idx_null] = 0
            
            #ret['samples'][idx_null,:,:] = 0
            #ret['best'][idx_null,:] = 0
            #ret['GR'][idx_null,:] = 0
            #ret['n_stars'][idx_null] = 0
        
        # Transform back to scalar response if user supplied scalar l, b
        if is_scalar:
            for key in ret.keys():
                ret[key] = ret[key][0]
        
        return ret
    
    def __call__(self, *args, **kwargs):
        return self.query(*args, **kwargs)


class SFDQuery():
    def __init__(self, map_dir):
        self.data = {}
        
        base_fname = os.path.join(map_dir, 'SFD_dust_4096')
        
        for pole in ['ngp', 'sgp']:
            fname = '{}_{}.fits'.format(base_fname, pole)
            with pyfits.open(fname) as hdulist:
                self.data[pole] = hdulist[0].header, hdulist[0].data
    
    def query(self, l, b, order=1):
        l = np.asarray(l)
        b = np.asarray(b)
        
        if l.shape != b.shape:
            raise ValueError('l.shape must equal b.shape')
        
        out = np.zeros_like(l, dtype='f4')
        
        for pole in ['ngp', 'sgp']:
            m = (b >= 0) if pole == 'ngp' else b < 0
            
            if np.any(m):
                header, data = self.data[pole]
                wcs = pywcs.WCS(header)
                
                if not m.shape: # Support for 0-dimensional arrays (scalars). Otherwise it barfs on l[m], b[m]
                    x, y = wcs.wcs_world2pix(l, b, 0)
                    out = map_coordinates(data, [[y], [x]], order=order, mode='nearest')[0]
                    continue
                
                x, y = wcs.wcs_world2pix(l[m], b[m], 0)
                out[m] = map_coordinates(data, [y, x], order=order, mode='nearest')
    
        return out
    
    def __call__(self, *args, **kwargs):
        return self.query(*args, **kwargs)


print 'Loading map query object ...'
map_query = MapQuery(os.path.join(data_path, 'dust-map-3d.h5'))
print 'Loading map images ...'
map_nside, map_pixval = load_images()
print 'Loading SFD ...'
sfd_query = SFDQuery(data_path)
print 'Done loading data.'


def test_find_data_idx(n):
    for k in xrange(n):
        l = np.random.random() * 10. + 175.
        b = np.random.random() * 10. - 5.
        
        print l, b
        
        idx = map_query._find_data_idx(l, b)
        
        if idx == -1:
            print 'Not found.\n'
            continue
        
        nside = map_query.locs['nside'][idx]
        hp_idx = map_query.locs['healpix_index'][idx]
        
        print nside, hp_idx, hputils.lb2pix(nside, l, b)
        print ''
        #print map_query(l, b)
        
        #ll, bb = hputils.pix2lb_scalar(nside, hp_idx)
        #
        #print l, ll
        #print b, bb
        #print ''

#test_find_data_idx(10000)
