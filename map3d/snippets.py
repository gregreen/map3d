#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  snippets.py
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

from pygments import highlight
from pygments.lexers.python import PythonLexer, PythonConsoleLexer
from pygments.formatters import HtmlFormatter

formatter = HtmlFormatter(style='friendly')



map_query_API = highlight(
"""
import json, requests

def query(lon, lat, coordsys='gal'):
    '''
    Send a line-of-sight reddening query to the Argonaut web server.
    
    Inputs:
      lon, lat: longitude and latitude, in degrees.
      coordsys: 'gal' for Galactic, 'equ' for Equatorial (J2000).
    
    Outputs a dictionary containing, among other things:
      'distmod':    The distance moduli that define the distance bins.
      'best':       The best-fit (maximum proability density)
                    line-of-sight reddening, in units of SFD-equivalent
                    E(B-V), to each distance modulus in 'distmod.' See
                    Schlafly & Finkbeiner (2011) for a definition of the
                    reddening vector (use R_V = 3.1).
      'samples':    Samples of the line-of-sight reddening, drawn from
                    the probability density on reddening profiles.
      'success':    1 if the query succeeded, and 0 otherwise.
      'converged':  1 if the line-of-sight reddening fit converged, and
                    0 otherwise.
      'n_stars':    # of stars used to fit the line-of-sight reddening.
      'DM_reliable_min':  Minimum reliable distance modulus in pixel.
      'DM_reliable_max':  Maximum reliable distance modulus in pixel.
    '''
    
    url = 'http://argonaut.rc.fas.harvard.edu/gal-lb-query-light'
    
    payload = {}
    
    if coordsys.lower() in ['gal', 'g']:
        payload['l'] = lon
        payload['b'] = lat
    elif coordsys.lower() in ['equ', 'e']:
        payload['ra'] = lon
        payload['dec'] = lat
    else:
        raise ValueError("coordsys '{0}' not understood.".format(coordsys))
    
    headers = {'content-type': 'application/json'}
    
    r = requests.post(url, data=json.dumps(payload), headers=headers)
    
    if r.status_code == 400:
        print '400 (Bad Request) Response Received from Argonaut:'
        print r.text
    
    return json.loads(r.text)
""",
PythonLexer(),
formatter)


map_query_API_example_single = highlight(
"""
>>> qresult = query(90, 10)
>>> 
>>> # See what information is returned for each pixel:
>>> print qresult.keys()
[u'b', u'GR', u'distmod', u'l', u'DM_reliable_max', u'ra', u'samples',
u'n_stars', u'converged', u'success', u'dec', u'DM_reliable_min', u'best']
>>> 
>>> print qresult['n_stars']
750
>>> print qresult['converged']
1
>>> print qresult['best']
[0.00426, 0.00678, 0.0074, 0.00948, 0.01202, 0.01623, 0.01815, 0.0245,
0.0887, 0.09576, 0.10139, 0.12954, 0.1328, 0.21297, 0.23867, 0.24461,
0.37452, 0.37671, 0.37684, 0.37693, 0.37695, 0.37695, 0.37696, 0.37698,
0.37698, 0.37699, 0.37699, 0.377, 0.37705, 0.37708, 0.37711]
""",
PythonConsoleLexer(),
formatter)


map_query_API_example_multiple = highlight(
"""
>>> qresult = query([45, 170, 250], [0, -20, 40])
>>> 
>>> print qresult['n_stars']
[352, 162, 254]
>>> print qresult['converged']
[1, 1, 1]
>>> # Look at the best fit for the first pixel:
>>> print qresult['best'][0]
[0.00545, 0.00742, 0.00805, 0.01069, 0.02103, 0.02718, 0.02955, 0.03305,
0.36131, 0.37278, 0.38425, 0.41758, 1.53727, 1.55566, 1.65976, 1.67286,
1.78662, 1.79262, 1.88519, 1.94605, 1.95938, 2.0443, 2.39438, 2.43858,
2.49927, 2.54787, 2.58704, 2.58738, 2.58754, 2.58754, 2.58755]
""",
PythonConsoleLexer(),
formatter)



h5_open_example = highlight(
"""
>>> import numpy as np
>>> import h5py
>>> 
>>> f = h5py.File('dust-map-3d.h5', 'r')
>>> pix_info = f['/pixel_info'][:]
>>> samples = f['/samples'][:]
>>> best_fit = f['/best_fit'][:]
>>> GR = f['/GRDiagnostic'][:]
>>> f.close()
>>> 
>>> print pix_info['nside']
[512 512 512 ..., 1024 1024 1024]
>>> 
>>> print pix_info['healpix_index']
[1461557 1461559 1461602 ..., 6062092 6062096 6062112]
>>> 
>>> print pix_info['n_stars']
[628 622 688 ..., 322 370 272]
>>> 
>>> # Best-fit E(B-V) in each pixel
>>> best_fit.shape  # (# of pixels, # of distance bins)
(2437292, 31)
>>> 
>>> # Get the best-fit E(B-V) in each distance bin for the first pixel
>>> best_fit[0]
array([ 0.00401   ,  0.00554   ,  0.012     ,  0.01245   ,  0.01769   ,
        0.02089   ,  0.02355   ,  0.03183   ,  0.04297   ,  0.08127   ,
        0.11928   ,  0.1384    ,  0.95464998,  0.9813    ,  1.50296998,
        1.55045998,  1.81668997,  1.86567998,  1.9109    ,  2.00281   ,
        2.01739001,  2.02519011,  2.02575994,  2.03046989,  2.03072   ,
        2.03102994,  2.03109002,  2.03109002,  2.03110003,  2.03110003,
        2.03111005], dtype=float32)
>>> 
>>> # Samples of E(B-V) from the Markov Chain
>>> samples.shape  # (# of pixels, # of samples, # of distance bins)
(2437292, 20, 31)
>>> 
>>> # The Gelman-Rubin convergence diagnostic in the first pixel.
>>> # Each distance bin has a separate value.
>>> # Typically, GR > 1.1 indicates non-convergence.
>>> GR[0]
array([ 1.01499999,  1.01999998,  1.01900005,  1.01699996,  1.01999998,
        1.01999998,  1.02400005,  1.01600003,  1.00800002,  1.00600004,
        1.00100005,  1.00199997,  1.00300002,  1.02499998,  1.01699996,
        1.00300002,  1.01300001,  1.00300002,  1.00199997,  1.00199997,
        1.00199997,  1.00199997,  1.00100005,  1.00100005,  1.00100005,
        1.00100005,  1.00100005,  1.00100005,  1.00100005,  1.00100005,
        1.00100005], dtype=float32)
""",
PythonConsoleLexer(),
formatter)



def main():
    import os
    script_dir = os.path.dirname(os.path.realpath(__file__))
    
    css = formatter.get_style_defs('.highlight').replace('.highlight', '.highlight pre')
    print css
    
    f = open(os.path.join(script_dir, 'static/css/pygment-highlight.css'), 'w')
    f.write(css)
    f.close()
    
    return 0

if __name__ == '__main__':
    main()

