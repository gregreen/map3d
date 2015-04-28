
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
       mode     :  The query mode ('full', 'lite' or 'sfd')
       message  :  Error message if success == False
    '''
    
    lon, lat = None, None
    coord_in = None
    mode = None
    n_max = None
    
    # Check the return mode
    if 'mode' in json:
        mode = json['mode'].lower()
        n_max = max_request_size.get(mode, None)
        
        if n_max == None:
            msg = 'Unkonwn query mode: "{}" (recognized modes: {})'.format(
                mode,
                ', '.join(['"{}"'.format(m) for m in max_request_size.keys()])
            )
            return {}, False, '', msg
    
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
        return {}, False, '', 'No coordinates found in request: Submit JSON with either (l,b) or (ra,dec).'
    
    coord_names = ('l','b') if coord_in == 'G' else ('ra','dec')
    
    # Extract lon and lat
    if array_like(lon):
        if not array_like(lat):
            return {}, False, '', '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        if len(lat) != len(lon):
            return {}, False, '', '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        if len(lon) > n_max:
            return {}, False, '', 'Requests limited to {0} coordinates at a time.'.format(n_max)
        
        try:
            lon = np.array(lon).astype('f4')
            lat = np.array(lat).astype('f4')
        except ValueError:
            return {}, False, '', 'Non-numeric coordinates detected.'
        
        if np.any((lat > 90.) | (lat < -90.)):
            return {}, False, '', '|{0}| > 90 degrees detected.'.format(coord_names[1])
    else:
        if array_like(lat):
            return {}, False, '', '{0} and {1} must have same number of dimensions.'.format(*coord_names)
        
        try:
            lon = float(lon)
            lat = float(lat)
        except ValueError:
            return {}, False, '', 'Non-numeric coordinates detected.'
        
        if (lat > 90.) or (lat < -90.):
            return {}, False, '', '|{0}| > 90 degrees detected.'.format(coord_names[1])
    
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
    
    return coords, True, mode, ''


def get_los(coords, mode='full', gen_table=False):
    los_data = mapdata.map_query(coords['l'], coords['b'], mode=mode)
    los_data['distmod'] = np.linspace(4., 19., 31)
    
    if array_like(los_data['n_stars']):
        los_data['success'] = (np.array(los_data['n_stars']) != 0).astype('u1')
    else:
        los_data['success'] = int(los_data['n_stars'] != 0)
    
    if gen_table:
        table_txt = los_to_ascii(coords, los_data)
        table_enc = json.dumps(encode_ascii(table_txt))
        
        return los_data, table_enc
    
    return los_data


def get_sfd(coords, decimals=5):
    ebv = mapdata.sfd_query(coords['l'], coords['b'])
    return {'EBV_SFD': ebv}


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
