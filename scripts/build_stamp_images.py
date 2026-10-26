#!/usr/bin/env python
"""Build the small maps used to draw postage stamps on the query page.

For each 3D map we compute reddening on an nside-512 nested HEALPix grid at the
map's stamp distances and store the result next to the map data. The web app
memory-maps these files, so serving a stamp costs no resident memory and never
touches the full map.

    python scripts/build_stamp_images.py --all
    python scripts/build_stamp_images.py --map bayestar2019 --force
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from map3d.maps import build_registry  # noqa: E402
from map3d.postage_stamp import StampImageStore  # noqa: E402

CHUNK = 200_000


def _mode_for(spec) -> str:
    return "median" if "median" in spec.modes else spec.default_mode


def build_map(spec, store: StampImageStore, nside: int, force: bool = False) -> Path | None:
    import healpy as hp
    from tqdm import tqdm

    if not spec.is_3d or not spec.stamp_distances:
        return None

    target = store.image_path(spec.name)
    if target.exists() and store.meta_path(spec.name).exists() and not force:
        print(f"[skip] {spec.name}: image cache already present (use --force to rebuild)")
        return target

    query = spec.factory()
    n_pix = hp.nside2npix(nside)
    lon, lat = hp.pix2ang(nside, np.arange(n_pix), lonlat=True, nest=True)

    pixval = np.empty((n_pix, len(spec.stamp_distances)), dtype="f4")
    mode = _mode_for(spec)

    t0 = time.time()
    for k, distance_pc in enumerate(spec.stamp_distances):
        for start in tqdm(
            range(0, n_pix, CHUNK), desc=f"{spec.name} {distance_pc:.0f} pc", leave=False
        ):
            stop = min(start + CHUNK, n_pix)
            coords = SkyCoord(
                lon[start:stop] * u.deg,
                lat[start:stop] * u.deg,
                distance=(distance_pc * u.pc).to(u.kpc),
                frame="galactic",
            )
            values = query(coords, mode=mode)
            pixval[start:stop, k] = np.asarray(values, dtype="f4") * spec.display_scale

    store.save(spec.name, nside, pixval, spec.stamp_distances)
    print(
        f"[built] {spec.name}: nside={nside}, {len(spec.stamp_distances)} distances, "
        f"{time.time() - t0:.1f} s"
    )
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--map", action="append", dest="maps", metavar="NAME")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--nside", type=int, default=None)
    args = parser.parse_args(argv)

    from dustmaps.std_paths import data_dir as dustmaps_data_dir

    from map3d.config import default_config

    config = default_config()
    registry = build_registry({"MAX_SAMPLES": config["MAX_SAMPLES"]})
    nside = args.nside or config["STAMP_NSIDE"]
    store = StampImageStore(
        Path(dustmaps_data_dir()) / "images", capacity=config["IMAGE_CACHE_SIZE"]
    )

    if not (args.maps or args.all):
        parser.error("pass --all or --map NAME")

    names = registry.names() if args.all else args.maps
    unknown = [n for n in names if n not in registry]
    if unknown:
        parser.error(f"unknown map(s): {', '.join(unknown)}")

    built = 0
    for name in names:
        spec = registry.spec(name)
        if build_map(spec, store, nside, force=args.force) is not None:
            built += 1

    print(f"\n{built} stamp image(s) available in {store.images_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
