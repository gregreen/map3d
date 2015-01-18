
import numpy as np
import healpy as hp

import json
import urllib
#from StringIO import StringIO


def get_los(map_query, l, b):
    mu = np.linspace(4., 19., 31).tolist()
    
    los_data = map_query(l, b)
    
    if los_data == None:
        best = np.zeros(len(mu)).tolist()
        samples = [best]
        n_stars = 0
        converged = 1
        table_enc = encode_ascii('')
        
        return mu, best, samples, n_stars, converged, table_enc
    
    best = los_data['best'].tolist()
    samples = los_data['samples'].tolist()
    n_stars = los_data['n_stars'].tolist()
    converged = int(np.all(los_data['GR'] < 1.2))
    
    table_txt = los_to_ascii(l, b, mu, best, samples, n_stars, converged)
    table_enc = encode_ascii(table_txt)
    
    return mu, best, samples, n_stars, converged, table_enc


def get_encoded_los(map_query, l, b):
    return [json.dumps(d) for d in get_los(map_query, l, b)]


def los_to_ascii(l, b, mu, best, samples, n_stars, converged, colwidth=6):
    # Pixel header
    txt  = '# Line-of-Sight Reddening Results\n'
    txt += '# ===============================\n'
    txt += '#\n'
    txt += '# Galactic coordinates (in degrees):\n'
    txt += '#     l = %.4f\n' % l
    txt += '#     b = %.4f\n' % b
    txt += '# Number of stars: %d\n' % (n_stars)
    txt += '# Fit converged: %s\n' % ('True' if converged else 'False')
    txt += '#\n'
    
    # Explanation
    txt += '# The table contains E(B-V) in magnitudes out to the specified distance moduli.\n'
    txt += '# Each column corresponds to a different distance modulus, and each row\n'
    txt += '# corresponds to a different sample. The first sample is the best fit, while\n'
    txt += '# the following samples are drawn from the posterior distribution of\n'
    txt += '# distance-reddening profiles.\n'
    txt += '#\n'
    txt += '# See Green et al. (2014) & Green et al. (2015) for a detailed description\n'
    txt += '# of how the line-of-sight reddening is computed.\n\n'
    
    n_rows = len(mu) + 1
    
    # Table column headings
    txt += 'SampleNo'.center(10)
    txt += '|'
    txt += ' DistanceModulus\n'
    
    txt += ''.center(10)
    txt += '|'
    
    for m in mu:
        txt += ('%.2f' % m).rjust(colwidth)
    
    txt += '\n'
    txt += '-' * (11 + len(mu)*colwidth)
    txt += '\n'
    
    # Best fit
    txt += 'BestFit'.center(10)
    txt += '|'
    
    for E in best:
        txt += ('%.3f' % E).rjust(colwidth)
    
    txt += '\n'
    
    # Samples
    for k,samp in enumerate(samples):
        txt += ('%d' % k).center(10)
        txt += '|'
        
        for E in samp:
            txt += ('%.3f' % E).rjust(colwidth)
        
        txt += '\n'
    
    return txt

def encode_ascii(txt):
    data = txt.encode('US-ASCII')
    data = 'data:text/plain;charset=US-ASCII,{0}'.format(urllib.quote(data))
    
    return data
