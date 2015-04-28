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

def query(lon, lat, coordsys='gal', mode='full'):
    '''
    Send a line-of-sight reddening query to the Argonaut web server.
    
    Inputs:
      lon, lat: longitude and latitude, in degrees.
      coordsys: 'gal' for Galactic, 'equ' for Equatorial (J2000).
      mode: 'full', 'lite' or 'sfd'
    
    In 'full' mode, outputs a dictionary containing, among other things:
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
    
    Less information is returned in 'lite' mode, while in 'sfd' mode,
    the Schlegel, Finkbeiner & Davis (1998) E(B-V) is returned.
    '''
    
    url = 'http://argonaut.rc.fas.harvard.edu/gal-lb-query-light'
    #url = 'http://127.0.0.1:5000/gal-lb-query-light'
    
    payload = {'mode': mode}
    
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
    
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print('Response received from Argonaut:')
        print(r.text)
        raise e
    
    print('Elapsed: {0} s'.format(r.elapsed.total_seconds()))
    print('Length: {0:.2f} kB'.format(float(r.headers['content-length'])/1024.))
    print('Encoding: {0}'.format(r.headers['content-encoding']))
    
    return json.loads(r.text)


def test_bad():
    query(90, 110., coordsys='equ')


def test_sfd_comp():
    import numpy as np
    import time
    import matplotlib.pyplot as plt
    
    N = 1000
    
    lon = 360. * np.random.random(N)
    lat = -30. + 120. * np.random.random(N)
    
    q1 = query(lon.tolist(), lat.tolist(), coordsys='equ', mode='sfd')
    q2 = query(lon.tolist(), lat.tolist(), coordsys='equ', mode='full')
    
    SFD = np.array(q1['EBV_SFD'])
    
    best = np.array(q2['best'])[:,-1]
    samples = np.array(q2['samples'])[:,:,-1]
    
    converged = np.all(np.array(q2['GR']) < 1.2, axis=1)
    success = (np.array(q2['success']) == 1)
    inbounds = (np.abs(np.array(q2['b'])) > 20.)
    
    idx0 = converged & success & inbounds
    idx1 = ~converged & success & inbounds
    
    print '(converged, nonconverged): ({}, {})'.format(np.sum(idx0), np.sum(idx1))
    
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1, aspect='equal')
    
    for n in range(samples.shape[1]):
        fSFD0 = 1. + 0.05 * np.random.normal(size=np.sum(idx0))
        fSFD1 = 1. + 0.05 * np.random.normal(size=np.sum(idx1))
        
        dSFD0 = 0.02 * np.random.normal(size=np.sum(idx0))
        dSFD1 = 0.02 * np.random.normal(size=np.sum(idx1))
        
        ax.scatter(SFD[idx0]*fSFD0 + dSFD0, samples[idx0,n], facecolor='b', edgecolor='none', alpha=0.10)
        ax.scatter(SFD[idx1]*fSFD1 + dSFD1, samples[idx1,n], facecolor='r', edgecolor='none', alpha=0.25)
    
    x = [0, np.percentile(best[idx0], 98.) * 1.2]
    
    ax.plot(x, x, 'g-', lw=2., alpha=0.25)
    
    ax.set_xlim(x)
    ax.set_ylim(x)
    
    plt.show()


def test_batch():
    import numpy as np
    import time
    
    N = 100
    lon = 360. * (np.random.random(N) - 0.5) #80. + 15. * (np.random.random(N) - 0.5)
    lat = 180 * (np.random.random(N) - 0.5) #15. * (np.random.random(N) - 0.5)
    
    t_start = time.time()
    q = query(lon.tolist(), lat.tolist(), coordsys='gal', mode='sfd')
    t_end = time.time()
    
    
    print ''
    
    for k in q.keys():
        v = q[k]
        txt = str(k)
        if hasattr(v, '__len__') and not isinstance(v, basestring):
            txt += ' ({})'.format(len(v))
        txt += ':'
        print txt
        print ''
        print v
        print ''
        print ''
        print ''
    
    
    print 't = %.4fs' % (t_end - t_start)


def test_single():
    import numpy as np
    import time
    
    N = 100
    l = 360. * (np.random.random(N) - 0.5)
    b = 180. * (np.random.random(N) - 0.5)
    
    t_start = time.time()
    
    for i,(ll,bb) in enumerate(zip(l[:10],b[:10])):
        pixel_data = query(ll, bb, coordsys='equ', mode='lite')
        
        print ''
        print i+1
        print pixel_data['l']
        print pixel_data['b']
        print pixel_data['converged']
        
        #time.sleep(0.5)
    
    t_end = time.time()
    
    print ''
    print 't   = %.4fs' % (t_end - t_start)
    print 't/N = %.4f s/request' % ((t_end - t_start) / N)
    print ''
    
    pixel_data = query(l.tolist(), b.tolist(), coordsys='e')
    print ''
    print np.array(pixel_data['ra']) - l
    print np.array(pixel_data['dec']) - b
    
    print query(180, 0).keys()
    
    return 0


def test_sfd():
    import numpy as np
    
    #ra, dec = 248.08527000, -24.51136000
    ra, dec = 150., -30.
    
    q = query(ra, dec, coordsys='equ', mode='sfd')
    
    q['l'] = np.mod(q['l'], 360.)
    q['A_B'] = q['EBV_SFD'] * 3.626
    
    print ' '.join(['{: ^10s}'.format(s) for s in ['RA', 'Dec', 'l', 'b', 'E(B-V)', 'A_B']])
    print ' '.join(['{: >10.6f}'.format(q[s]) for s in ['ra', 'dec', 'l', 'b', 'EBV_SFD', 'A_B']])
    print ''


def main():
    #test_bad()
    #test_batch()
    #test_single()
    #test_sfd_comp()
    
    test_sfd()
    
    return 0

if __name__ == '__main__':
    main()

