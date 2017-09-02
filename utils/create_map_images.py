#!/usr/bin/env python

from __future__ import print_function, division

import numpy as np
import healpy as hp
import h5py

from contextlib import closing
from progressbar import ProgressBar


def resample_healpix(pix_val, nside_target):
    """
    Resamples a nested HEALPix map to the target nside.
    The input map, ``pix_val'', will possibly be modified in the process.
    """
    nside_input = hp.pixelfunc.npix2nside(len(pix_val))

    if nside_input == nside_target:
        return pix_val
    elif nside_input > nside_target: # downsample
        downsample_factor = (nside_input // nside_target)**2
        n_pixels_target = hp.pixelfunc.nside2npix(nside_target)
        pix_val.shape = (n_pixels_target, downsample_factor)
        return np.nanmean(pix_val, axis=1)
    else: # upsample
        upsample_factor = (nside_target // nside_input)**2
        # pix_val.shape = (pix_val.size, 1)
        return np.repeat(pix_val, upsample_factor)


def multires2uniform(pix_nside, pix_idx, pix_val, nside_target):
    nside_levels = np.unique(pix_nside)
    n_pix_target = hp.pixelfunc.nside2npix(nside_target)

    pix_val_target = np.empty(
        (len(nside_levels), n_pix_target),
        dtype=pix_val.dtype)

    for k,nside in enumerate(nside_levels):
        idx = (pix_nside == nside)

        n_pix_nside = hp.pixelfunc.nside2npix(nside)
        pix_val_nside = np.empty(n_pix_nside, dtype=pix_val.dtype)
        pix_val_nside[:] = np.nan
        pix_val_nside[pix_idx[idx]] = pix_val[idx]

        pix_val_target[k,:] = resample_healpix(pix_val_nside, nside_target)

    return np.nanmean(pix_val_target, axis=0)


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(
        description="Generate uniform-nside rendering of map",
        add_help=True)
    parser.add_argument("in_fname", metavar="INPUT.h5",
                        type=str, help="Input map filename.")
    parser.add_argument("out_fname", metavar="OUTPUT.h5",
                        type=str, help="Output filename.")
    parser.add_argument("--nside", "-n", metavar="NSIDE",
                        type=int, default=1024,
                        help="HEALPix nside of output map.")
    parser.add_argument("--decimals", "-d", metavar="# OF DIGITS",
                        type=int, default=4,
                        help="# of decimal digits to round output to.")
    args = parser.parse_args()

    print("Resampling individual distances ...")

    with closing(h5py.File(args.in_fname, 'r')) as f:
        n_pix, n_samples, n_dists = f['samples'].shape
        pix_info = f['pixel_info'][:]

        n_pix_out = hp.pixelfunc.nside2npix(args.nside)
        pix_val_out = np.empty((n_pix_out, n_dists), dtype='f4')

        bar = ProgressBar(redirect_stdout=False,
                          max_value=n_dists)

        for k in bar(range(n_dists)):
            pix_val = np.median(f['samples'][:,:,k], axis=1)

            pix_val_out[:,k] = multires2uniform(
                pix_info['nside'],
                pix_info['healpix_index'],
                pix_val, args.nside)

    print("Writing output ...")

    pix_val_out = np.round(pix_val_out, decimals=args.decimals)

    with closing(h5py.File(args.out_fname, 'w')) as f:
        dset = f.create_dataset(
            '/reddening',
            data=pix_val_out,
            chunks=True,
            compression='gzip',
            compression_opts=3)
        dset.attrs['nside'] = args.nside

    return 0


if __name__ == '__main__':
    main()
