"""Sphere-to-plane projections and HEALPix helpers used for postage stamps.

Extracted from the old ``hputils`` module: only the gnomonic projection and two
thin HEALPix wrappers are used by the rasterizer, so the plotting helpers and
demo code are gone.
"""

from __future__ import annotations

import numpy as np


def lb2pix(nside: int, l, b, nest: bool = True):
    """Galactic (l, b) in degrees → HEALPix pixel index."""
    import healpy as hp

    return hp.ang2pix(nside, l, b, lonlat=True, nest=nest)


def pix2lb(nside: int, ipix, nest: bool = True):
    """HEALPix pixel index → Galactic (l, b) in degrees."""
    import healpy as hp

    return hp.pix2ang(nside, ipix, lonlat=True, nest=nest)


class Gnomonic_projection:
    """Gnomonic projection of the sphere onto a tangent plane."""

    def __init__(self, phi_0: float = 0.0, lam_0: float = 180.0, fov: float = 90.0):
        self.phi_0 = np.radians(phi_0)
        self.lam_0 = np.radians(lam_0)
        self.fov = np.radians(fov)

        self.cp0 = np.cos(self.phi_0)
        self.sp0 = np.sin(self.phi_0)

    def proj(self, phi, lam, ret_bounds: bool = False):
        p = phi
        lon = lam

        cp = np.cos(p)
        sp = np.sin(p)

        cDl = np.cos(lon - self.lam_0)
        sDl = np.sin(lon - self.lam_0)

        with np.errstate(divide="ignore", invalid="ignore"):
            a = 1.0 / (self.sp0 * sp + self.cp0 * cp * cDl)
            x = a * cp * sDl
            y = a * (self.cp0 * sp - self.sp0 * cp * cDl)

        if ret_bounds:
            with np.errstate(invalid="ignore"):
                out_of_bounds = np.arccos(np.clip(1.0 / a, -1.0, 1.0)) > self.fov
            return x, y, out_of_bounds

        return x, y

    def inv(self, x, y):
        rho = np.sqrt(x**2.0 + y**2.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            c = np.arctan(rho)
            cc = np.cos(c)
            sc = np.sin(c)

            phi = np.arcsin(cc * self.sp0 + y * sc * self.cp0 / rho)
            lam = self.lam_0 + np.arctan2(
                x * sc, rho * self.cp0 * cc - y * self.sp0 * sc
            )

        out_of_bounds = np.abs(c) > self.fov
        return phi, lam, out_of_bounds
