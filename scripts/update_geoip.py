#!/usr/bin/env python
"""Download the free DB-IP Lite city database for anonymous usage statistics.

The database maps an IP address to a country and a city centroid, which is all
we keep (see PRIVACY.md). DB-IP Lite City is CC BY 4.0 and needs no account or
license key; it is refreshed monthly.

    python scripts/update_geoip.py                 # installs this month's file
    python scripts/update_geoip.py --month 2026-09 # a specific release

Schedule it monthly, e.g. a cron entry on the instance:

    17 4 3 * * cd /srv/map3d/app && \\
      docker compose -f docker/docker-compose.yml run --rm --no-deps \\
      --entrypoint python web scripts/update_geoip.py
"""

from __future__ import annotations

import argparse
import gzip
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_URL = "https://download.db-ip.com/free/dbip-city-lite-{month}.mmdb.gz"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--month", default=time.strftime("%Y-%m"),
                        help="Release month, YYYY-MM (default: current month)")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL template")
    parser.add_argument("--output", default=None,
                        help="Destination .mmdb (default: MAP3D_GEOIP_DB or $STATE_DIR)")
    args = parser.parse_args(argv)

    from map3d.config import default_config

    config = default_config()
    target = Path(args.output or config["GEOIP_DB"])
    target.parent.mkdir(parents=True, exist_ok=True)

    url = args.url.format(month=args.month)
    print(f"downloading {url}")

    with tempfile.TemporaryDirectory(dir=config["TMP_DIR"]) as scratch:
        gz_path = Path(scratch) / "dbip.mmdb.gz"
        mmdb_path = Path(scratch) / "dbip.mmdb"

        request = urllib.request.Request(
            url, headers={"User-Agent": "map3d-geoip-updater/1.0 (+argonaut.skymaps.info)"}
        )
        with urllib.request.urlopen(request, timeout=300) as response, open(gz_path, "wb") as fh:
            shutil.copyfileobj(response, fh)

        print(f"decompressing {gz_path.stat().st_size / 1e6:.0f} MB")
        with gzip.open(gz_path, "rb") as src, open(mmdb_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

        # Sanity-check before replacing the live database.
        try:
            import geoip2.database

            with geoip2.database.Reader(str(mmdb_path)) as reader:
                reader.city("8.8.8.8")
        except Exception as err:
            print(f"downloaded file is not a usable MMDB: {err}", file=sys.stderr)
            return 1

        os.replace(mmdb_path, target)

    print(f"installed {target} ({target.stat().st_size / 1e6:.0f} MB)")
    print("restart the web service so workers pick up the new database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
