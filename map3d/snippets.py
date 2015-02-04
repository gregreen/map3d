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

def query(l, b):
    '''
    Send a line-of-sight reddening query to the Argonaut web server.
    
    Inputs:
      l, b: Galactic coordinates, in degrees.
    
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
    '''
    
    url = 'http://argonaut.rc.fas.harvard.edu/gal-lb-query-light'
    
    payload = {'l': l, 'b': b}
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
[u'b', u'success', u'l', u'samples', u'n_stars', u'converged',
u'distmod', u'best']
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
>>> f = h5py.File('compact_10samp.h5', 'r')
>>> locs = f['/locations'][:]
>>> sample_data = f['/piecewise'][:]
>>> f.close()
>>> 
>>> print locs['nside']
[512 512 512 ..., 512 512 512]
>>> 
>>> print locs['healpix_index']
[1638079 1638107 1638108 ..., 1726393 1726441 1726442]
>>> 
>>> print locs['n_stars']
[583 514 483 ..., 614 597 603]
>>> 
>>> best = sample_data[:,1,1:]  # The best-fit E(B-V)
>>> 
>>> # Get the best-fit E(B-V) in each distance bin for the first pixel
>>> best[0]
array([ 0.00870818,  0.01387209,  0.01712639,  0.0259521 ,  0.03068264,
        0.04779445,  0.41486135,  0.42843446,  0.50651842,  0.54525876,
        0.55168515,  0.6681751 ,  0.68385363,  0.7205106 ,  0.72992986,
        0.73316681,  0.85566115,  0.88557971,  0.93445128,  0.93879509,
        1.101686  ,  1.11637986,  1.12184167,  1.12560546,  1.12607443,
        1.12609482,  1.12610161,  1.12611556,  1.1261183 ,  1.12612486,
        1.12613201], dtype=float32)
>>> 
>>> # Samples of E(B-V) from the Markov Chain
>>> samples = sample_data[:, 2:, 1:]
>>> 
>>> samples.shape  # (# of pixels, # of samples, # of distance bins)
(7581, 9, 31)
>>> 
>>> # The Gelman-Rubin (GR) convergence diagnostic
>>> GR = sample_data[:, 0, 1:]
>>> 
>>> # The GR diagnostic in the first pixel. Each distance bin has
>>> # a separate value. Typically, GR > 1.1 indicates non-convergence.
>>> GR[0]
array([ 1.00627136,  1.0167731 ,  1.02478695,  1.02237451,  1.02512574,
        1.0170598 ,  1.00679624,  1.00653064,  1.01060462,  1.00396991,
        1.00202465,  1.00423181,  1.00346017,  1.01117611,  1.01044476,
        1.00302243,  1.00246012,  1.00939417,  1.00406373,  1.01277184,
        1.00545788,  1.01066709,  1.01512182,  1.0160321 ,  1.01495719,
        1.01469755,  1.01468885,  1.01468158,  1.01467431,  1.01465094,
        1.01465344], dtype=float32)
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

