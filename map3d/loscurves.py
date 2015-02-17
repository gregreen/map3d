
from map3d import mapdata

import numpy as np
import healpy as hp

import json
import urllib

from utils import array_like
import hputils


def get_coords(json, max_request_size):
    '''
    Takes JSON containing coordinate specifications, and returns
       dict     :  containing l, b, ra, dec
       success  :  True if the coordinates are well-formed
       message  :  Error message if success == False
    '''
    
    lon, lat = None, None
    coord_in = None
    
    # Check that either (l,b) or (ra,dec) are provided
    if ('l' in json) and ('b' in json):
        lon = json['l']
        lat = json['b']
        coord_in = 'G'
    elif ('ra' in json) and ('dec' in json):
        lon = json['ra']
        lat = json['dec']
        coord_in = 'C'
    else:
        return {}, False, 'No coordinates found in request: Submit JSON with either (l,b) or (ra,dec).'
    
    coord_names = ('l','b') if coord_in == 'G' else ('ra','dec')
    
    # Extract lon and lat
    if array_like(lon):
        if not array_like(lat):
            print '1'
            return {}, False, '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        if len(lat) != len(lon):
            print '2'
            return {}, False, '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        if len(lon) > max_request_size:
            print '3'
            return {}, False, 'Requests limited to {0} coordinates at a time.'.format(max_request_size)
        
        try:
            lon = np.array(lon).astype('f4')
            lat = np.array(lat).astype('f4')
        except ValueError:
            print '4'
            return {}, False, 'Non-numeric coordinates detected.'
    else:
        if array_like(lat):
            print '5'
            return {}, False, '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        
        try:
            lon = float(lon)
            lat = float(lat)
        except ValueError:
            print '6'
            return {}, False, 'Non-numeric coordinates detected.'
    
    # Check for |latitude| > 90 degrees
    if np.any((lat > 90.) | (lat < -90.)):
        print lat
        print lat[(lat > 90.) | (lat < -90.)]
        
        print '7'
        return {}, False, '|{0}| > 90 degrees detected.'.format(coord_names[1])
    
    # Construct coordinate dictionary
    coords = {}
    
    if coord_in == 'G':
        coords['l'] = lon
        coords['b'] = lat
        coords['ra'], coords['dec'] = hputils.transform_coords(lon, lat, 'G', 'C')
    else:
        coords['ra'] = lon
        coords['dec'] = lat
        coords['l'], coords['b'] = hputils.transform_coords(lon, lat, 'C', 'G')
    
    return coords, True, ''



def get_los(coords, decimals=5):
    los_data = mapdata.map_query(coords['l'], coords['b'])
    los_data['distmod'] = np.linspace(4., 19., 31)
    
    #best = los_data['best']
    #samples = los_data['samples']
    #n_stars = los_data['n_stars']
    #DM_reliable_min = locs_data['DM_reliable_min']
    
    #axis = len(los_data['GR'].shape) - 1
    #converged = np.array(np.all(los_data['GR'] < 1.2, axis=axis)).astype('u1').tolist()
    
    table_enc = u''
    
    if not mapdata.array_like(coords['l']):
        table_txt = los_to_ascii(coords, los_data)
        table_enc = json.dumps(encode_ascii(table_txt))
        
        #converged = int(converged)
    
    # Round floats to requested number of decimal places
    for key in los_data.keys():
        if issubclass(los_data[key].dtype.type, np.integer):
            #print 'Not a float array: "{0}"'.format(key)
            los_data[key] = los_data[key].tolist()
        else:#elif issubclass(los_data[key].dtype.type, np.float):
            #print 'Rounding float array "{0}"'.format(key)
            los_data[key] = np.around(los_data[key].tolist(), decimals=decimals).tolist()
    
    # Encode as JSON string
    #if encode:
    #    for key in los_data.keys():
    #        los_data[key] = json.dumps(los_data[key])
    
    #best = np.around(best.tolist(), decimals=decimals).tolist()
    #samples = np.around(samples.tolist(), decimals=decimals).tolist()
    #n_stars = np.around(n_stars.tolist(), decimals=decimals).tolist()
    
    #return mu, best, samples, n_stars, converged, table_enc
    
    return los_data, table_enc


def get_encoded_los(coords):
    return [json.dumps(d) for d in get_los(coords)]


def los_to_ascii(coords, los_data, colwidth=6):
    # Pixel header
    txt  = '# Line-of-Sight Reddening Results\n'
    txt += '# ===============================\n'
    txt += '#\n'
    txt += '# Galactic coordinates (in degrees):\n'
    txt += '#     l = %.4f\n' % (coords['l'])
    txt += '#     b = %.4f\n' % (coords['b'])
    txt += '# Equatorial (J2000) coordinates (in degrees):\n'
    txt += '#     ra = %.4f\n' % (coords['ra'])
    txt += '#     dec = %.4f\n' % (coords['dec'])
    txt += '# Number of stars: %d\n' % (los_data['n_stars'])
    txt += '# Reliable distance moduli:\n'
    txt += '#     min: %.2f\n' % (los_data['DM_reliable_min'])
    txt += '#     max: %.2f\n' % (los_data['DM_reliable_max'])
    txt += '# Fit converged: %s\n' % ('True' if los_data['converged'] else 'False')
    txt += '#\n'
    
    # Explanation
    txt += '# The table contains E(B-V) in magnitudes out to the specified distance moduli.\n'
    txt += '# Each column corresponds to a different distance modulus, and each row\n'
    txt += '# corresponds to a different sample. The first sample is the best fit, while\n'
    txt += '# the following samples are drawn from the posterior distribution of\n'
    txt += '# distance-reddening profiles.\n'
    txt += '# \n'
    txt += '# See Green et al. (2014) & Green et al. (2015) for a detailed description\n'
    txt += '# of how the line-of-sight reddening is computed.\n'
    txt += '# \n'
    txt += '# Use coefficients in Table 6 of Schlafly & Finkbeiner (2011) to convert to\n'
    txt += '# extinction in various bands (note that A_B - A_V != 1 for E(B-V) = 1; E(B-V)\n'
    txt += '# is strictly a parameter name here).\n\n'
    
    n_rows = len(los_data['distmod']) + 1
    
    # Table column headings
    txt += 'SampleNo'.center(10)
    txt += '|'
    txt += ' DistanceModulus\n'
    
    txt += ''.center(10)
    txt += '|'
    
    for dm in los_data['distmod']:
        txt += ('%.2f' % dm).rjust(colwidth)
    
    txt += '\n'
    txt += '-' * (11 + len(los_data['distmod'])*colwidth)
    txt += '\n'
    
    # Best fit
    txt += 'BestFit'.center(10)
    txt += '|'
    
    for E in los_data['best']:
        txt += ('%.3f' % E).rjust(colwidth)
    
    txt += '\n'
    
    # Samples
    for k,samp in enumerate(los_data['samples']):
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
