"""Synthetic map objects and files used by the tests."""

from __future__ import annotations

import h5py
import healpy as hp
import numpy as np
from astropy import units as u


def make_bayestar_h5(path, nside: int = 8, n_samples: int = 3) -> None:
    """Write a tiny file in the layout BayestarQuery expects (repacked HDF5)."""
    dm_edges = np.array([4.0, 6.0, 8.0, 10.0, 12.0], dtype="f8")
    n_dists = dm_edges.size
    n_pix = hp.nside2npix(nside)

    pixel_info = np.empty(
        n_pix,
        dtype=[
            ("nside", "i4"),
            ("healpix_index", "i8"),
            ("DM_reliable_min", "f4"),
            ("DM_reliable_max", "f4"),
            ("converged", "bool"),
        ],
    )
    pixel_info["nside"] = nside
    pixel_info["healpix_index"] = np.arange(n_pix, dtype="i8")
    pixel_info["DM_reliable_min"] = dm_edges[0]
    pixel_info["DM_reliable_max"] = dm_edges[-1]
    pixel_info["converged"] = True

    ramp = (np.arange(n_dists, dtype="f4") + 1.0) * 0.1  # 0.1, 0.2, ... E(g−r)
    samples = np.broadcast_to(ramp, (n_pix, n_samples, n_dists)).copy()
    samples += np.arange(n_samples, dtype="f4")[None, :, None] * 0.01
    best_fit = np.broadcast_to(ramp, (n_pix, n_dists)).copy()

    with h5py.File(path, "w") as f:
        info = f.create_dataset("pixel_info", data=pixel_info)
        info.attrs["DM_bin_edges"] = dm_edges
        f.create_dataset("samples", data=samples, chunks=(16, n_samples, n_dists))
        f.create_dataset("best_fit", data=best_fit, chunks=(16, n_dists))
        f.attrs["repacked"] = True


class Fake2DQuery:
    """Stand-in for SFD/Planck/CSFD: returns a constant reddening."""

    def __init__(self, name: str = "fake", value: float = 0.12):
        self.name = name
        self.value = value

    def __call__(self, coords, return_flags=False, **kwargs):
        values = np.full(np.shape(coords), self.value, dtype="f8")
        if not return_flags:
            return values
        # CSFD's 'cosmology' bit, which is the only one set in this fake.
        return values, np.full(np.shape(coords), 4, dtype="u1")


class Fake3DDistanceSamples:
    """Stand-in for Edenhofer 2023: integrated extinction with 4 samples."""

    distances = np.linspace(100.0, 1250.0, 24) * u.pc
    _n_samples = 4

    # Spread of the fake posterior, as a fraction of the mean
    _spread = 0.1

    def __call__(self, coords, mode="mean", **kwargs):
        if not hasattr(coords.distance, "kpc"):
            raise ValueError("This map requires a distance.")
        d = np.atleast_1d(coords.distance.to_value("pc"))
        mean = 5e-4 * d
        if mode == "mean":
            return mean
        if mode == "std":
            return self._spread * mean
        if mode == "samples":
            offsets = np.linspace(-1.0, 1.0, self._n_samples) * self._spread
            return mean[..., np.newaxis] * (1.0 + offsets)
        if mode == "random_sample":
            return mean
        raise ValueError(f"unsupported mode {mode!r}")

class FakeFootprintQuery:
    """Stand-in for DECaPS: data only inside a small patch of sky.

    Mirrors what the real map reports through its flags: inside the footprint the
    fit converges, on the rim the pixel is infilled from its neighbors and may
    not have converged, and everywhere else there is no data at all.
    """

    distances = np.linspace(200.0, 8000.0, 6) * u.pc
    _n_samples = 2

    # (l_min, l_max, b_min, b_max) of the patch that has its own fits, and the
    # strip just outside it that is infilled from them.
    footprint = (115.0, 125.0, 5.0, 15.0)
    infilled = (125.0, 128.0)

    def _state(self, coord):
        l = float(coord.l.deg) % 360.0
        b = float(coord.b.deg)
        l_min, l_max, b_min, b_max = self.footprint
        if l_min <= l <= l_max and b_min <= b <= b_max:
            return "inside"
        i_min, i_max = self.infilled
        if i_min < l <= i_max and b_min <= b <= b_max:
            return "infilled"
        return "outside"

    def _profile(self, coord):
        # A monotonic curve, so a profile is distinguishable from a constant
        return np.linspace(0.1, 0.6, self.distances.size) * (1.0 + 0.01 * coord.l.deg)

    def __call__(self, coords, mode="mean", return_flags=False, **kwargs):
        one = np.ndim(coords) == 0
        coords_1d = np.atleast_1d(coords)
        states = [self._state(c) for c in coords_1d]

        n = len(coords_1d)
        n_dist = self.distances.size
        if mode == "samples":
            out = np.empty((n, self._n_samples, n_dist), dtype="f8")
            for i, (c, state) in enumerate(zip(coords_1d, states)):
                out[i] = self._profile(c) if state != "outside" else np.nan
        else:
            out = np.empty((n, n_dist), dtype="f8")
            for i, (c, state) in enumerate(zip(coords_1d, states)):
                out[i] = self._profile(c) if state != "outside" else np.nan
        if one:
            out = out[0]

        if not return_flags:
            return out

        flags = np.empty(
            n,
            dtype=[
                ("converged", "bool"),
                ("infilled", "bool"),
                ("min_reliable_distmod", "f4"),
                ("max_reliable_distmod", "f4"),
            ],
        )
        for i, state in enumerate(states):
            flags["converged"][i] = state == "inside"
            flags["infilled"][i] = state == "infilled"
            flags["min_reliable_distmod"][i] = 4.0 if state != "outside" else np.nan
            flags["max_reliable_distmod"][i] = 12.0 if state != "outside" else np.nan
        if one:
            flags = flags[:1]
        return out, flags
