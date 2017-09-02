
from map3d import mapdata

import numpy as np
import healpy as hp

import ujson as json
import urllib

from utils import array_like
import hputils


def encode_ascii(txt):
    data = txt.encode('US-ASCII')
    data = 'data:text/plain;charset=US-ASCII,{0}'.format(urllib.quote(data))

    return data


def los_ascii_summary(coords, samples, best, flags,
                      distmod=np.linspace(4.,19.,31),
                      colwidth=6, encode=True):

    # Coordinate description
    if coords.frame.name == 'galactic':
        coord_txt = (
            "# Galactic coordinates (in degrees):\n"
            "#     l = {gal.l.deg:.4f}\n"
            "#     b = {gal.b.deg:.4f}\n"
            ).format(gal=coords)
    elif coords.frame.name in ('icrs', 'fk5', 'fk4', 'fk4noeterms'):
        coord_txt = (
            "# Equatorial (J2000, {frame:s}) coordinates (in degrees):\n"
            "#     ra = {equ.ra.deg:.4f}\n"
            "#     dec = {equ.dec.deg:.4f}\n"
            ).format(equ=coords, frame=str(coords.frame.name.upper()))

    # Pixel header
    header = (
        "#\n"
        "# Line-of-Sight Reddening Results\n"
        "# ===============================\n"
        "#\n"
        "# {coord_txt:s}"
        "#\n"
        "# Reliable distance moduli:\n"
        "#     min: {min_reliable_distmod:.2f}\n"
        "#     max: {max_reliable_distmod:.2f}\n"
        "# Fit converged: {converged:}\n"
        ).format(
            coord_txt=coord_txt,
            min_reliable_distmod=flags['min_reliable_distmod'],
            max_reliable_distmod=flags['max_reliable_distmod'],
            converged=flags['converged'])

    # Explanation
    explanation = (
        "#\n"
        "# The table contains E(B-V) in magnitudes out to the specified distance moduli.\n"
        "# Each column corresponds to a different distance modulus, and each row\n"
        "# corresponds to a different sample. The first sample is the best fit, while\n"
        "# the following samples are drawn from the posterior distribution of\n"
        "# distance-reddening profiles.\n"
        "#\n"
        "# See Green et al. (2014) & Green et al. (2015) for a detailed description\n"
        "# of how the line-of-sight reddening is computed.\n"
        "#\n"
        "# Use coefficients in Table 6 of Schlafly & Finkbeiner (2011) to convert to\n"
        "# extinction in various bands (note that A_B - A_V != 1 for E(B-V) = 1; E(B-V)\n"
        "# is strictly a parameter name here).\n"
        "#\n")

    # Table column headings
    table = 'SampleNo'.center(10) + '| DistanceModulus\n'
    table += ''.center(10) + '|'

    # Distance modulus labels
    table += ''.join(['{:.2f}'.format(dm).rjust(colwidth) for dm in distmod])
    table += '\n' + '-' * (11 + len(distmod)*colwidth) + '\n'

    # Best fit
    table += 'BestFit'.center(10) + '|'

    table += ''.join(['{:.3f}'.format(E).rjust(colwidth) for E in best])
    table += '\n'

    # Samples
    for k,samp in enumerate(samples):
        table += '{:^10d}'.format(k) + '|'
        table += ''.join(['{: >6.3f}'.format(E) for E in samp])
        table += '\n'

    if encode:
        return encode_ascii(header + explanation + table)

    return header + explanation + table
