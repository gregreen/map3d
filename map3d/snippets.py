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
from pygments.lexers.idl import IDLLexer
from pygments.formatters import HtmlFormatter

formatter = HtmlFormatter(style='friendly')


map_query_API = {}

map_query_API['python-2.x'] = highlight(
"""
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

    url = 'http://argonaut.skymaps.info/gal-lb-query-light'

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

    return json.loads(r.text)
""",
PythonLexer(),
formatter)


map_query_API['IDL'] = highlight(
"""
;+
; NAME:
;   query_argonaut
;
; PURPOSE:
;   Query the Argonaut server for 3D dust information or SFD
;
; CALLING SEQUENCE:
;   qresult = query_argonaut(/struct, /debug, _extra=coords)
;
; INPUTS:
;   ra, dec   : numeric scalars or arrays [deg]
;     OR
;   l, b      : numeric scalars or arrays [deg]
;   mode      : 'full', 'lite', or 'sfd'.  Default to 'full'
;   structure : set this keyword to return structure instead of hash
;   debug     : set to return timing information
;
; OUTPUTS:
;   qresult   : a hash (or structure, if /structure set) containing
;  'distmod':    The distance moduli that define the distance bins.
;  'best':       The best-fit (maximum probability density)
;                  line-of-sight reddening, in units of SFD-equivalent
;                  E(B-V), to each distance modulus in 'distmod.' See
;                  Schlafly & Finkbeiner (2011) for a definition of the
;                  reddening vector (use R_V = 3.1).
;  'samples':    Samples of the line-of-sight reddening, drawn from
;                  the probability density on reddening profiles.
;  'success':    1 if the query succeeded, and 0 otherwise.
;  'converged':  1 if the line-of-sight reddening fit converged, and
;                  0 otherwise.
;  'n_stars':    # of stars used to fit the line-of-sight reddening.
;  'DM_reliable_min':  Minimum reliable distance modulus in pixel.
;  'DM_reliable_max':  Maximum reliable distance modulus in pixel.
;
; EXAMPLES:
;   IDL> qresult = query_argonaut(l=90, b=10)
;   IDL> help,qresult
;   QRESULT         HASH  <ID=1685  NELEMENTS=13>
;   IDL> qresult = query_argonaut(l=90, b=10, /struct)
;   IDL> help,qresult
;   ** Structure <d76608>, 13 tags, length=5776, data length=5776, refs=1:
;      GR              DOUBLE    Array[31]
;      SUCCESS         LONG64                         1
;      N_STARS         LONG64                       750
;      DEC             DOUBLE           54.568690
;      DM_RELIABLE_MAX DOUBLE           15.189000
;      CONVERGED       LONG64                         1
;      DISTMOD         DOUBLE    Array[31]
;      L               DOUBLE           90.000000
;      B               DOUBLE           10.000000
;      RA              DOUBLE          -54.585789
;      BEST            DOUBLE    Array[31]
;      DM_RELIABLE_MIN DOUBLE           6.7850000
;      SAMPLES         DOUBLE    Array[20, 31]
;
; COMMENTS:
;   - Any keywords other than "struct" or "debug" go into the
;       coords structure.
;   - Must call either with ra=, dec= or l=, b=.
;   - Angles are in degrees and can be arrays.
;   - JSON support introduced in IDL 8.2 (Jan, 2013) is required.
;
;   - THIS CODE RETURNS SFD-EQUIVALENT E(B-V)!
;       See Schlafly & Finkbeiner 2011) for conversion factors.
;       E(B-V)_Landolt is approximately 0.86*E(B-V)_SFD.
;
; REVISION HISTORY:
;   2015-Feb-26 - Written by Douglas Finkbeiner, CfA
;
;----------------------------------------------------------------------
function argo_json_serialize, struc

  ntags = n_tags(struc)
  key = tag_names(struc)
  val = strarr(ntags)

  for i=0L, ntags-1 do begin
     if size(struc.(i), /tname) EQ 'STRING' then $
        val[i] = '"'+key[i]+'":"'+struc.(i)+'"' $
     else begin
        arr = string(struc.(i), format='(F12.7)')+','
        arr[0]='['+arr[0]
        arr[-1] = repstr(arr[-1], ',', '')+']'
        val[i] = '"'+key[i]+'":'+strjoin(arr)
     endelse
  endfor

; -------- put it together
  for i=0L, ntags-2 do val[i]=val[i]+','
  string='{'+strjoin(val)+'}'

  return, string
end


function query_argonaut, struct=struct, debug=debug, _extra=coords

; -------- Check IDL version
  if !version.release lt 8.2 then begin
     message, 'IDL '+!version.release+' may lack JSON support', /info
     return, 0
  endif

  t0=systime(1)
; -------- Check inputs
  verb = keyword_set(debug)
  if n_tags(coords) GE 2 then tags = tag_names(coords) else tags=['', '']
  if ~((total((tags eq 'RA')+(tags eq 'DEC')) eq 2) or $
       (total((tags eq 'L') +(tags eq 'B')) eq 2)) then begin
     print, 'Must call with coordinates, e.g.'
     print, 'qresult = query_argonaut(ra=3.25, dec=4.5) or '
     print, 'qresult = query_argonaut(l=90, b=10)'
     return, 0
  endif
  ncoords = n_elements(coords.(0)) > n_elements(coords.(1))

; -------- Convert input parameters to lower case JSON string
  data = strlowcase(argo_json_serialize(coords))
  if verb then print, 'JSON serialize   :', systime(1)-t0, ' sec', format='(A,F8.3,A)'

; -------- Specify URL
  url  = 'http://argonaut.rc.fas.harvard.edu/gal-lb-query-light'

; -------- Create a new url object and set header
  oUrl = OBJ_NEW('IDLnetUrl')
  oUrl.SetProperty, HEADER = 'Content-Type: application/json'
  oUrl.SetProperty, encode=2            ; request gzipped response

; -------- Query Argonaut, send output to tmpfile
  tmpfile = filepath('argo-'+string(randomu(iseed,/double)*1D9,$
                                    format='(I9.9)'), /tmp)
  out = oUrl.Put(data, url=url, /buffer, /post, filename=tmpfile)
  if verb then print, 'Server query time:', systime(1)-t0, ' sec', format='(A,F8.3,A)'

; -------- Parse output to hash or structure
  result = keyword_set(struct) ? json_parse(out, /tostruct, /toarray) : $
                                 json_parse(out)
  if verb then print, 'Total time:       ', systime(1)-t0, ' sec', format='(A,F8.3,A)'

; -------- Clean up
  obj_destroy, oUrl
  file_delete, out

  return, result
end
""",
IDLLexer(),
formatter)


map_query_API_example_single = {}

map_query_API_example_single['python-2.x'] = highlight(
"""
>>> # Query the Galactic coordinates (l, b) = (90, 10):
>>> qresult = query(90, 10, coordsys='gal')
>>> 
>>> # See what information is returned for each pixel:
>>> qresult.keys()
[u'b', u'GR', u'distmod', u'l', u'DM_reliable_max', u'ra', u'samples',
u'n_stars', u'converged', u'success', u'dec', u'DM_reliable_min', u'best']
>>> 
>>> qresult['n_stars']
750
>>> qresult['converged']
1
>>> # Get the best-fit E(B-V) in each distance slice
>>> qresult['best']
[0.00426, 0.00678, 0.0074, 0.00948, 0.01202, 0.01623, 0.01815, 0.0245,
0.0887, 0.09576, 0.10139, 0.12954, 0.1328, 0.21297, 0.23867, 0.24461,
0.37452, 0.37671, 0.37684, 0.37693, 0.37695, 0.37695, 0.37696, 0.37698,
0.37698, 0.37699, 0.37699, 0.377, 0.37705, 0.37708, 0.37711]
>>> 
>>> # See the distance modulus of each distance slice
>>> qresult['distmod']
[4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5,
11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0, 16.5,
17.0, 17.5, 18.0, 18.5, 19.0]
""",
PythonConsoleLexer(),
formatter)

map_query_API_example_single['IDL'] = highlight(
"""
IDL> qresult = argonaut_query(l=90, b=10)
IDL> print, qresult.keys()
GR
success
n_stars
dec
DM_reliable_max
converged
distmod
l
b
ra
best
DM_reliable_min
samples
IDL> print, qresult['n_stars']
                   750
IDL> print, qresult['converged']
                     1
IDL> print, qresult['best'].toarray()
    0.0042600000    0.0067800000    0.0074000000    0.0094800000     0.012020000
     0.016230000     0.018150000     0.024500000     0.088700000     0.095760000
      0.10139000      0.12954000      0.13280000      0.21297000      0.23867000
      0.24461000      0.37452000      0.37671000      0.37684000      0.37693000
      0.37695000      0.37695000      0.37696000      0.37698000      0.37698000
      0.37699000      0.37699000      0.37700000      0.37705000      0.37708000
      0.37711000
IDL> print, qresult['distmod'].toarray()
             4.0             4.5             5.0             5.5             6.0
             6.5             7.0             7.5             8.0             8.5
             9.0             9.5            10.0            10.5            11.0
            11.5            12.0            12.5            13.0            13.5
            14.0            14.5            15.0            15.5            16.0
            16.5            17.0            17.5            18.0            18.5
            19.0
""",
IDLLexer(),
formatter)


map_query_API_example_multiple = {}

map_query_API_example_multiple['python-2.x'] = highlight(
"""
>>> qresult = query([45, 170, 250], [0, -20, 40])
>>> 
>>> qresult['n_stars']
[352, 162, 254]
>>> qresult['converged']
[1, 1, 1]
>>> # Look at the best fit for the first pixel:
>>> qresult['best'][0]
[0.00545, 0.00742, 0.00805, 0.01069, 0.02103, 0.02718, 0.02955, 0.03305,
0.36131, 0.37278, 0.38425, 0.41758, 1.53727, 1.55566, 1.65976, 1.67286,
1.78662, 1.79262, 1.88519, 1.94605, 1.95938, 2.0443, 2.39438, 2.43858,
2.49927, 2.54787, 2.58704, 2.58738, 2.58754, 2.58754, 2.58755]
""",
PythonConsoleLexer(),
formatter)

map_query_API_example_multiple['IDL'] = highlight(
"""
IDL> qresult = argonaut_query(l=[45, 170, 250], b=[0, -20, 40])
IDL> print, qresult['n_stars']
                   352
                   162
                   254
IDL> print, qresult['converged']
                     1
                     1
                     1
IDL> print, qresult['best',0].toarray()
    0.0054500000    0.0074200000    0.0080500000     0.010690000     0.021030000
     0.027180000     0.029550000     0.033050000      0.36131000      0.37278000
      0.38425000      0.41758000       1.5372700       1.5556600       1.6597600
       1.6728600       1.7866200       1.7926200       1.8851900       1.9460500
       1.9593800       2.0443000       2.3943800       2.4385800       2.4992700
       2.5478700       2.5870400       2.5873800       2.5875400       2.5875400
       2.5875500
""",
IDLLexer(),
formatter)


map_query_API_example_lite = {}

map_query_API_example_lite['python-2.x'] = highlight(
"""
>>> qresult = query(180, 0, coordsys='gal', mode='lite')
>>> qresult.keys()
[u'b', u'success', u'distmod', u'sigma', u'median', u'l',
u'DM_reliable_max', u'ra', u'n_stars', u'converged', u'dec',
u'DM_reliable_min', u'best']
>>> 
>>> # Get the median E(B-V) to each distance slice:
>>> qresult['median']
[0.0204, 0.02747, 0.03027, 0.03036, 0.03047, 0.05214, 0.05523, 0.0748,
0.07807, 0.10002, 0.13699, 0.2013, 0.20158, 0.20734, 0.23129, 0.73734,
0.76125, 0.83905, 0.90236, 1.05944, 1.08085, 1.11408, 1.11925, 1.12212,
1.12285, 1.12289, 1.12297, 1.12306, 1.12308, 1.12309, 1.12312]
>>> 
>>> # Get the standard deviation of E(B-V) in each slice
>>> # (actually, half the difference between the 84th and 16th percentiles):
>>> qresult['sigma']
[0.03226, 0.03476, 0.03452, 0.03442, 0.03439, 0.03567, 0.03625, 0.0317,
0.03238, 0.03326, 0.05249, 0.0401, 0.03919, 0.03278, 0.08339, 0.05099,
0.03615, 0.04552, 0.05177, 0.03678, 0.03552, 0.05246, 0.05055, 0.05361,
0.05422, 0.0538, 0.05381, 0.05381, 0.0538, 0.0538, 0.05379]
""",
PythonConsoleLexer(),
formatter)

map_query_API_example_lite['IDL'] = highlight(
"""
IDL> qresult = query_argonaut(l=180, b=0, mode='lite', /struct)
IDL> help,qresult
** Structure <405ff58>, 13 tags, length=1064, data length=1064, refs=1:
   DM_RELIABLE_MAX DOUBLE    Array[1]
   DM_RELIABLE_MIN DOUBLE    Array[1]
   B               DOUBLE    Array[1]
   BEST            DOUBLE    Array[1, 31]
   CONVERGED       LONG64    Array[1]
   DEC             DOUBLE    Array[1]
   DISTMOD         DOUBLE    Array[31]
   L               DOUBLE    Array[1]
   MEDIAN          DOUBLE    Array[1, 31]
   N_STARS         LONG64    Array[1]
   RA              DOUBLE    Array[1]
   SIGMA           DOUBLE    Array[1, 31]
   SUCCESS         LONG64    Array[1]

; Get the median E(B-V) to each distance slice:

IDL> print,reform(qresult.median)
     0.020400000     0.027470000     0.030270000     0.030360000     0.030470000
     0.052140000     0.055230000     0.074800000     0.078070000      0.10002000
      0.13699000      0.20130000      0.20158000      0.20734000      0.23129000
      0.73734000      0.76125000      0.83905000      0.90236000       1.0594400
       1.0808500       1.1140800       1.1192500       1.1221200       1.1228500
       1.1228900       1.1229700       1.1230600       1.1230800       1.1230900
       1.1231200

; Get the standard deviation of E(B-V) in each slice
; (actually, half the difference between the 84th and 16th percentiles):

IDL> print,reform(qresult.sigma)
     0.032260000     0.034760000     0.034520000     0.034420000     0.034390000
     0.035670000     0.036250000     0.031700000     0.032380000     0.033260000
     0.052490000     0.040100000     0.039190000     0.032780000     0.083390000
     0.050990000     0.036150000     0.045520000     0.051770000     0.036780000
     0.035520000     0.052460000     0.050550000     0.053610000     0.054220000
     0.053800000     0.053810000     0.053810000     0.053800000     0.053800000
     0.053790000
""",
IDLLexer(),
formatter)


map_query_API_example_SFD = {}

map_query_API_example_SFD['python-2.x'] = highlight(
"""
>>> qresult = query([0, 10, 15], [75, 80, 85], coordsys='gal', mode='sfd')
>>> 
>>> qresult.keys()
[u'EBV_SFD', u'b', u'dec', u'l', u'ra']
>>> 
>>> # E(B-V), in magnitudes:
>>> qresult['EBV_SFD']
[0.02119, 0.01813, 0.01352]
""",
PythonConsoleLexer(),
formatter)

map_query_API_example_SFD['IDL'] = highlight(
"""
IDL> qresult = query_argonaut(l=[0, 10, 15], b=[75, 80, 85], mode='sfd', /struct)
IDL> help,qresult
** Structure <16ae1a8>, 5 tags, length=120, data length=120, refs=1:
   EBV_SFD         DOUBLE    Array[3]
   B               DOUBLE    Array[3]
   DEC             DOUBLE    Array[3]
   L               DOUBLE    Array[3]
   RA              DOUBLE    Array[3]

; E(B-V) in magnitudes:

IDL> print,qresult.ebv_sfd
     0.021190000     0.018130000     0.013520000
""",
IDLLexer(),
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
>>> print(pix_info['nside'])
[512 512 512 ..., 1024 1024 1024]
>>> 
>>> print(pix_info['healpix_index'])
[1461557 1461559 1461602 ..., 6062092 6062096 6062112]
>>> 
>>> print(pix_info['n_stars'])
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



reindex_example = [highlight(txt, PythonConsoleLexer(), formatter) for txt in ([
"""
>>> import numpy as np
>>> import h5py
>>> import healpy as hp
>>> import matplotlib.pyplot as plt
>>> 
>>> # Open the file and extract pixel information and median reddening in the far limit
>>> f = h5py.File('dust-map-3d.h5', 'r')
>>> pix_info = f['/pixel_info'][:]
>>> EBV_far_median = np.median(f['/samples'][:,:,-1], axis=1)
>>> f.close()
""",

"""
>>> # Construct an empty map at the highest HEALPix resolution present in the map
>>> nside_max = np.max(pix_info['nside'])
>>> n_pix = hp.pixelfunc.nside2npix(nside_max)
>>> pix_val = np.empty(n_pix, dtype='f8')
>>> pix_val[:] = np.nan
""",

"""
>>> # Fill the upsampled map
>>> for nside in np.unique(pix_info['nside']):
...     # Get indices of all pixels at current nside level
...     idx = pix_info['nside'] == nside
... 
...     # Extract E(B-V) of each selected pixel
...     pix_val_n = EBV_far_median[idx]
... 
...     # Determine nested index of each selected pixel in upsampled map
...     mult_factor = (nside_max/nside)**2
...     pix_idx_n = pix_info['healpix_index'][idx] * mult_factor
... 
...     # Write the selected pixels into the upsampled map
...     for offset in range(mult_factor):
...         pix_val[pix_idx_n+offset] = pix_val_n[:]
""",

"""
>>> # Plot the results using healpy's matplotlib routines
>>> hp.visufunc.mollview(pix_val, nest=True, xsize=4000,
                         min=0., max=4., rot=(130., 0.),
                         format=r'$%g$',
                         title=r'$\mathrm{E} ( B-V \, )$',
                         unit='$\mathrm{mags}$')
>>> plt.show()
"""
])]


#
# dustmaps package
#

dustmaps_local_API = highlight(
"""
>>> from astropy.coordinates import SkyCoord
>>> import astropy.units as units
>>> from dustmaps.bayestar import BayestarQuery
>>> 
>>> bayestar = BayestarQuery(version='bayestar2017') # Bayestar2017 is the default
>>> coords = SkyCoord(90.*units.deg, 30.*units.deg,
...                   distance=100.*units.pc, frame='galactic')
>>> 
>>> reddening = bayestar(coords, mode='median')
>>> print(reddening)
0.00621500005946
""",
PythonConsoleLexer(),
formatter)

dustmaps_remote_API = highlight(
"""
>>> from astropy.coordinates import SkyCoord
>>> import astropy.units as units
>>> from dustmaps.bayestar import BayestarWebQuery
>>> 
>>> bayestar = BayestarWebQuery(version='bayestar2017')
>>> coords = SkyCoord(90.*units.deg, 30.*units.deg,
...                   distance=100.*units.pc, frame='galactic')
>>> 
>>> reddening = bayestar(coords, mode='random_sample')
>>> print(reddening)
0.00590000022203
""",
PythonConsoleLexer(),
formatter)

dustmaps_SFD_API = highlight(
"""
>>> from astropy.coordinates import SkyCoord
>>> import astropy.units as units
>>> from dustmaps.sfd import SFDWebQuery
>>> 
>>> sfd = SFDWebQuery()
>>> coords = SkyCoord(45.*units.deg, 45.*units.deg, frame='icrs') # Equatorial
>>> 
>>> ebv_sfd = sfd(coords)
>>> print(ebv_sfd)
0.22122733295
""",
PythonConsoleLexer(),
formatter)

dustmaps_array_API = highlight(
"""
>>> import numpy as np
>>> from astropy.coordinates import SkyCoord
>>> import astropy.units as units
>>> from dustmaps.bayestar import BayestarWebQuery
>>> 
>>> bayestar = BayestarWebQuery() # Uses Bayestar2017 by default.
>>> 
>>> l = np.array([30., 60., 90.])
>>> b = np.array([-15., 10., 70.])
>>> d = np.array([0.1, 3., 0.5])
>>> coords = SkyCoord(l*units.deg, b*units.deg,
...                   distance=d*units.kpc, frame='galactic')
>>> 
>>> reddening = bayestar(coords, mode='percentile', pct=90.)
>>> print(reddening)
[ 0.085303    0.22474321  0.03297591]
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
