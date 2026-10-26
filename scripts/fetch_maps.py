#!/usr/bin/env python
"""Download the dust maps served by this site.

Uses the dustmaps fetchers, which download, verify and repack each map for
memory-mapped access. Every fetcher defaults to ``clobber=False``, so running
this on an already-populated data directory is a no-op: it only downloads maps
that are genuinely missing. That makes it safe to call on every deploy.

Examples
--------
    python scripts/fetch_maps.py --all
    python scripts/fetch_maps.py --map bayestar2019 --map decaps
    python scripts/fetch_maps.py --verify --report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from map3d.maps import build_registry  # noqa: E402


def _fetchers():
    """Map name -> callable that downloads the data for that map."""
    from dustmaps import bayestar, csfd, decaps, edenhofer2023, planck, sfd

    return {
        "bayestar2015": lambda clobber: bayestar.fetch(version="bayestar2015", clobber=clobber),
        "bayestar2017": lambda clobber: bayestar.fetch(version="bayestar2017", clobber=clobber),
        "bayestar2019": lambda clobber: bayestar.fetch(version="bayestar2019", clobber=clobber),
        "decaps": lambda clobber: decaps.fetch(clobber=clobber),
        "edenhofer2023": lambda clobber: edenhofer2023.fetch(
            clobber=clobber, fetch_samples=True
        ),
        "sfd": lambda clobber: sfd.fetch(),
        "csfd": lambda clobber: csfd.fetch(clobber=clobber),
        "planck-tau353": lambda clobber: planck.fetch(which="2013"),
        "planck-radiance": lambda clobber: planck.fetch(which="2013"),
        "planck-ebv": lambda clobber: planck.fetch(which="2013"),
        "planck-gnilc": lambda clobber: planck.fetch(which="GNILC"),
    }


def _human(size: float) -> str:
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def verify(registry) -> tuple[list[str], list[str]]:
    """Construct every query object; report which maps are usable."""
    ok, failed = [], []
    for name in registry.names():
        spec = registry.spec(name)
        try:
            query = spec.factory()
        except Exception as err:
            failed.append(f"{name}: {type(err).__name__}: {err}")
            continue

        handle = getattr(query, "_f", None)
        if handle is not None and hasattr(handle, "attrs"):
            if not handle.attrs.get("repacked", False):
                failed.append(
                    f"{name}: HDF5 file is not repacked (memory-mapped queries will be slow)"
                )
                continue
        ok.append(name)
    return ok, failed


def report(data_dir: Path) -> None:
    print(f"\nData directory: {data_dir}")
    total = 0
    for path in sorted(data_dir.iterdir()):
        if path.is_dir():
            size = _dir_size(path)
            total += size
            print(f"  {path.name:<28} {_human(size):>10}")
    print(f"  {'total':<28} {_human(total):>10}")

    images = data_dir / "images"
    if images.is_dir():
        print("\nPre-built postage-stamp images:")
        for path in sorted(images.glob("*.npy")):
            print(f"  {path.stem:<28} {_human(path.stat().st_size):>10}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--map", action="append", dest="maps", metavar="NAME", help="Map to fetch (repeatable)."
    )
    parser.add_argument("--all", action="store_true", help="Fetch every map in the registry.")
    parser.add_argument("--verify", action="store_true", help="Only check that maps load.")
    parser.add_argument("--report", action="store_true", help="Print on-disk sizes.")
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    args = parser.parse_args(argv)

    from dustmaps.std_paths import data_dir as dustmaps_data_dir

    data_dir = Path(dustmaps_data_dir())
    registry = build_registry({"MAX_SAMPLES": 5})

    if not (args.maps or args.all or args.verify or args.report):
        parser.error("nothing to do: pass --all, --map NAME, --verify or --report")

    names = registry.names() if args.all else list(args.maps or [])
    unknown = [n for n in names if n not in registry]
    if unknown:
        parser.error(f"unknown map(s): {', '.join(unknown)}")

    if names and not args.verify:
        fetchers = _fetchers()
        seen = set()
        for name in names:
            spec = registry.spec(name)
            if spec.name in seen:
                continue
            seen.add(spec.name)
            fetcher = fetchers.get(spec.name)
            if fetcher is None:
                print(f"[skip] {name}: no fetcher registered")
                continue
            print(f"[fetch] {name}", flush=True)
            fetcher(args.force)

    if args.verify or names:
        ok, failed = verify(registry)
        print(f"\nverified: {len(ok)} map(s) usable")
        for name in ok:
            print(f"  [ok]   {name}")
        for message in failed:
            print(f"  [fail] {message}")
        if failed and args.verify:
            return 1

    if args.report:
        report(data_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
