#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  query_argonaut.py
#  
#  Copyright 2015 Gregory M. Green
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

import json, requests

def query(l, b):
    '''
    Send a line-of-sight reddening query to the Argonaut web server.
    
    Inputs:
      l, b (scalars): Galactic coordinates, in degrees.
    
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
      'table_data': An ASCII string with a table and comments
                    summarizing the line-of-sight reddening information.
    '''
    
    #url = 'http://argonaut.rc.fas.harvard.edu/gal-lb-query-light'
    url = 'http://127.0.0.1:5000/gal-lb-query-light'
    
    payload = {'l': l, 'b': b}
    headers = {'content-type': 'application/json'}
    
    r = requests.post(url, data=json.dumps(payload), headers=headers)
    
    print r.headers
    
    if r.status_code == 400:
        print '400 (Bad Request) Response Received from Argonaut:'
        print r.text
    
    return json.loads(r.text)
    


def main():
    import numpy as np
    import time
    
    N = 2000
    l = 360. * np.random.random(N)
    b = 180. * np.random.random(N) - 90.
    
    t_start = time.time()
    
    for i,(ll,bb) in enumerate(zip(l,b)):
        pixel_data = query(ll, bb)
        print i+1
        #time.sleep(0.5)
    
    t_end = time.time()
    
    print ''
    print 't   = %.4fs' % (t_end - t_start)
    print 't/N = %.4f s/request' % ((t_end - t_start) / N)
    print ''
    
    return 0

if __name__ == '__main__':
    main()

