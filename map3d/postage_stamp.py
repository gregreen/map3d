"""Postage-stamp images of cumulative reddening around a line of sight.

The images are rasterized from small, pre-computed maps (nside 512 medians at a
few distances per map) built offline by ``scripts/build_stamp_images.py``. Those
files are memory-mapped, so serving a stamp costs no extra resident memory.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .rasterize import MapRasterizerFast

log = logging.getLogger(__name__)

IMG_SHAPE = (500, 500)
FOV = 15.0
RADIUS = 0.5 * FOV
MASK_COLOR = (202, 222, 219)


@dataclass(frozen=True)
class StampImage:
    map_name: str
    nside: int
    pixval: np.ndarray  # (n_pixels, n_distances)
    distances: np.ndarray  # (n_distances,) in pc


class StampImageStore:
    def __init__(self, images_dir: str | Path, capacity: int = 4):
        self.images_dir = Path(images_dir)
        self.capacity = max(1, int(capacity))
        self._cache: OrderedDict[str, StampImage] = OrderedDict()
        self._rasterizers: dict[int, MapRasterizerFast] = {}

    # -- storage ----------------------------------------------------------

    def image_path(self, map_name: str) -> Path:
        return self.images_dir / f"{map_name}.npy"

    def meta_path(self, map_name: str) -> Path:
        return self.images_dir / f"{map_name}.json"

    def available(self, map_name: str) -> bool:
        return self.image_path(map_name).is_file() and self.meta_path(map_name).is_file()

    def available_maps(self) -> list[str]:
        if not self.images_dir.is_dir():
            return []
        return sorted(p.stem for p in self.images_dir.glob("*.npy"))

    def load(self, map_name: str) -> StampImage | None:
        if map_name in self._cache:
            self._cache.move_to_end(map_name)
            return self._cache[map_name]

        if not self.available(map_name):
            return None

        try:
            meta = json.loads(self.meta_path(map_name).read_text())
            pixval = np.load(self.image_path(map_name), mmap_mode="r")
        except Exception as err:
            log.warning("could not load stamp image map=%s error=%s", map_name, err)
            return None

        image = StampImage(
            map_name=map_name,
            nside=int(meta["nside"]),
            pixval=pixval,
            distances=np.asarray(meta["distances"], dtype="f8"),
        )
        self._cache[map_name] = image
        while len(self._cache) > self.capacity:
            self._cache.popitem(last=False)
        return image

    def save(
        self,
        map_name: str,
        nside: int,
        pixval: np.ndarray,
        distances,
        tmp_dir: str | Path | None = None,
    ) -> None:
        """Write an image cache atomically (uncompressed .npy so we can mmap it)."""
        self.images_dir.mkdir(parents=True, exist_ok=True)
        target = self.image_path(map_name)
        scratch = Path(tmp_dir or self.images_dir)
        scratch.mkdir(parents=True, exist_ok=True)

        tmp_data = scratch / f".{map_name}.npy.tmp"
        tmp_meta = scratch / f".{map_name}.json.tmp"
        try:
            with open(tmp_data, "wb") as fh:
                np.save(fh, np.ascontiguousarray(pixval, dtype="f4"), allow_pickle=False)
            tmp_meta.write_text(
                json.dumps(
                    {
                        "map": map_name,
                        "nside": int(nside),
                        "distances": [float(d) for d in distances],
                    },
                    indent=2,
                )
            )
            tmp_data.replace(target)
            tmp_meta.replace(self.meta_path(map_name))
        finally:
            tmp_data.unlink(missing_ok=True)
            tmp_meta.unlink(missing_ok=True)
        self._cache.pop(map_name, None)

    # -- rasterization ----------------------------------------------------

    def _rasterizer(self, nside: int) -> MapRasterizerFast:
        if nside not in self._rasterizers:
            self._rasterizers[nside] = MapRasterizerFast(nside, IMG_SHAPE, fov=FOV)
        return self._rasterizers[nside]

    def postage_stamps(
        self,
        map_name: str,
        l: float,
        b: float,
        dists: list[float] | None = None,
        difference: bool = False,
    ) -> list[np.ndarray] | None:
        image = self.load(map_name)
        if image is None:
            return None

        if dists is None:
            indices = list(range(image.distances.size))
        else:
            indices = [int(np.argmin(np.abs(image.distances - d))) for d in dists]

        pix_val = [np.asarray(image.pixval[:, k], dtype="f4") for k in indices]
        img = self._rasterizer(image.nside).rasterize(pix_val, l, b)
        return normalize_stamps(img, difference=difference)


def normalize_stamps(img: np.ndarray, difference: bool = False) -> np.ndarray:
    img = np.array(img, dtype="f4")
    if img.size == 0:
        return img

    if difference:
        if img.shape[0] >= 2:
            img[1:] -= img[:-1]
        idx = np.isfinite(img)
        if not np.any(idx):
            return img
        vmax = np.percentile(img[idx], 99.5)
    else:
        idx = np.isfinite(img[-1])
        if not np.any(idx):
            return img
        vmax = np.percentile(img[-1][idx], 99.0)

    if vmax > 0:
        img *= 1.0 / vmax
    return img


def encode_image(img_arr: np.ndarray, c_mask=MASK_COLOR) -> str:
    """Encode a normalized stamp as a base64 JPEG data URI."""
    from PIL import Image

    img_arr = np.asarray(img_arr, dtype="f4").T[::-1, :]
    nan_mask = ~np.isfinite(img_arr)

    gray = np.clip(np.nan_to_num(img_arr, nan=0.0), 0.0, 1.0)
    gray = (255.0 * gray).astype(np.uint8)

    if np.any(nan_mask):
        color = np.empty(gray.shape + (3,), dtype=np.uint8)
        for k in range(3):
            color[:, :, k] = gray
            color[nan_mask, k] = c_mask[k]
        image = Image.fromarray(color)
    else:
        image = Image.fromarray(gray)

    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=40, subsampling=0)  # 4:4:4 avoids color fringing at the NaN mask
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/jpeg;base64," + data
