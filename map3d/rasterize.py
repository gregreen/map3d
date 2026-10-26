"""Fast rasterization of single-resolution HEALPix maps into image planes."""

from __future__ import annotations

import numpy as np

from .projections import Gnomonic_projection, lb2pix


class MapRasterizerFast:
    """Rasterizes single-resolution HEALPix maps.

    The mapping between display-space pixels and HEALPix pixels is computed once
    per field of view, so rasterizing additional distance slices is a single
    fancy-index operation.
    """

    def __init__(
        self,
        nside: int,
        img_shape: tuple[int, int],
        fov: float = 10.0,
        nest: bool = True,
        proj: Gnomonic_projection | None = None,
    ):
        import healpy as hp

        self.img_shape = img_shape
        self.proj = Gnomonic_projection() if proj is None else proj
        self.nside = nside
        self.nest = nest
        self._hp = hp

        # Coordinates of the corners of the field of view in projection space
        l = np.radians(np.array([-0.5 * fov, 0.5 * fov, 0.0, 0.0]))
        b = np.radians(np.array([0.0, 0.0, -0.5 * fov, 0.5 * fov]))
        x, y = self.proj.proj(b, l)
        x_min, x_max = x[:2]
        y_max, y_min = y[2:]

        x_size, y_size = img_shape
        x, y = np.mgrid[0:x_size, 0:y_size].astype(np.float32) + 0.5
        x = (x_min + (x_max - x_min) * x / float(x_size)).flatten()
        y = (y_min + (y_max - y_min) * y / float(y_size)).flatten()

        b, lam, self.clip_mask = self.proj.inv(x, y)
        self.l_0 = 180.0 - 180.0 / np.pi * lam
        self.b_0 = b * 180.0 / np.pi

    def _get_pix_index(self, l_cent: float, b_cent: float):
        l, b = self.l_0, self.b_0

        if (l_cent != 0.0) or (b_cent != 0.0):
            rot = self._hp.rotator.Rotator(
                rot=(l_cent, b_cent, 0.0), eulertype="XYZ", deg=True
            ).get_inverse()
            l, b = rot(l, b, lonlat=True)

        return lb2pix(self.nside, l, b, nest=self.nest)

    def rasterize(self, map_list, l_cent: float, b_cent: float):
        hp_idx = self._get_pix_index(l_cent, b_cent)

        img_stack = np.zeros(
            (len(map_list), self.img_shape[0], self.img_shape[1]),
            dtype=np.asarray(map_list[0]).dtype,
        )
        flat = img_stack.reshape(len(map_list), -1)
        for k, m in enumerate(map_list):
            flat[k] = m[hp_idx]

        return img_stack
