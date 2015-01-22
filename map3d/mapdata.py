
import os
import h5py
import numpy as np

import hputils


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
        self.locs = f['/locations'][:]
        
        # Load samples by nside
        self.sample_data = f['/piecewise'][:]
        
        f.close()
        
        # Get healpix indices at each nside level
        sort_idx = np.argsort(self.locs, order=['nside', 'healpix_index'])
        
        self.nside_levels = np.unique(self.locs['nside'])
        self.hp_idx_sorted = []
        self.data_idx = []
        
        start_idx = 0
        
        for nside in self.nside_levels:
            end_idx = np.searchsorted(self.locs['nside'], nside,
                                      side='right', sorter=sort_idx)
            
            idx = sort_idx[start_idx:end_idx]
            
            self.hp_idx_sorted.append(self.locs['healpix_index'][idx])
            self.data_idx.append(idx)
            
            start_idx = end_idx
    
    def _find_data_idx(self, l, b):
        # Search at each nside
        for k,nside in enumerate(self.nside_levels):
            ipix = hputils.lb2pix(nside, l, b, nest=True)
            
            idx = np.searchsorted(self.hp_idx_sorted[k], ipix, side='left')
            
            if idx >= self.hp_idx_sorted[k].size:
                continue
            
            if self.hp_idx_sorted[k][idx] == ipix:
                #print 'nside:', nside
                #print 'ipix:', ipix
                #print 'Found at:', self.data_idx[k][idx]
                #print self.locs[self.data_idx[k][idx]]
                
                return self.data_idx[k][idx]
        
        return -1
    
    def query(self, l, b):
        idx = self._find_data_idx(l, b)
        
        if idx == -1:
            return None
        
        ret = {}
        ret['samples'] = self.sample_data[idx, 2:, 1:]
        ret['best'] = self.sample_data[idx, 1, 1:]
        ret['GR'] = self.sample_data[idx, 0, 1:]
        ret['n_stars'] = self.locs['n_stars'][idx]
        
        return ret
    
    def __call__(self, *args):
        return self.query(*args)


print 'Loading map query object ...'
map_query = MapQuery(os.path.join(data_path, 'compact_10samp.h5'))
print 'Loading map images ...'
map_nside, map_pixval = load_images()
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
