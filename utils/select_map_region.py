#!/usr/bin/env python

from __future__ import print_function, division

import numpy as np
import healpy as hp
import h5py

from contextlib import closing
from progressbar import ProgressBar


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(
        description="Select a small region of a Bayestar map.",
        add_help=True)
    parser.add_argument("in_fname", metavar="INPUT.h5",
                        type=str, help="Input map filename.")
    parser.add_argument("out_fname", metavar="OUTPUT.h5",
                        type=str, help="Output filename.")
    args = parser.parse_args()

    with closing(h5py.File(args.in_fname, 'r')) as f_in:
        print('Determining which pixels to keep ...')

        pix_info = f_in['pixel_info'][:]

        coords = np.empty((pix_info.size,2), dtype='f8')
        nside_levels = np.unique(pix_info['nside'])

        for nside in nside_levels:
            idx = (pix_info['nside'] == nside)
            theta, phi = hp.pixelfunc.pix2ang(
                nside,
                pix_info['healpix_index'][idx].astype('i8'),
                nest=True)

            coords[idx,0] = np.degrees(phi)         # l (deg)
            coords[idx,1] = 90. - np.degrees(theta) # b (deg)

        idx = (np.abs(coords[:,0] - 80.) < 5.) & (np.abs(coords[:,1] < 5.))

        print('Keeping {:d} pixels.'.format(np.sum(idx)))
        print('Copying data into output file ...')

        with closing(h5py.File(args.out_fname, 'w')) as f_out:
            for dset_key in f_in.keys():
                print('Copying {} ...'.format(dset_key))

                if dset_key == 'samples':
                    data = f_in[dset_key][:,:5,:]
                else:
                    data = f_in[dset_key][:]

                data = data[idx]

                dset = f_out.create_dataset(
                    dset_key,
                    data=data,
                    chunks=True,
                    compression='gzip',
                    compression_opts=3)

                for attr_key, attr_val in f_in[dset_key].attrs.items():
                    dset.attrs[attr_key] = attr_val

    return 0


if __name__ == '__main__':
    main()
