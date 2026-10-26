"""Code samples shown on the usage page, highlighted once at import time."""

from __future__ import annotations

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers.python import PythonConsoleLexer, PythonLexer

formatter = HtmlFormatter(style="friendly")
styles = formatter.get_style_defs(".highlight")


def _python(source: str) -> str:
    return highlight(source.strip("\n"), PythonLexer(), formatter)


def _console(source: str) -> str:
    return highlight(source.strip("\n"), PythonConsoleLexer(), formatter)


map_query_API: dict[str, str] = {}

map_query_API["python"] = _python(
    """
import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord
from dustmaps.bayestar import BayestarWebQuery

# Point the web query at this service (HTTP -> HTTPS in the next release)
bayestar = BayestarWebQuery(api_url='https://argonaut.skymaps.info/api/v2/')

coords = SkyCoord(
    150.*u.deg, 20.*u.deg,
    distance=[0.5, 1., 2.]*u.kpc,
    frame='galactic')

# Best-fit reddening in each requested distance bin
reddening = bayestar(coords, mode='best')

# Many coordinates in a single request
coords = SkyCoord(np.random.uniform(0., 360., 1000)*u.deg,
                  np.random.uniform(-90., 90., 1000)*u.deg,
                  frame='galactic')
median = bayestar(coords, mode='median')
"""
)

map_query_API["local"] = _python(
    """
from dustmaps.bayestar import BayestarQuery

# Uses the locally downloaded map; memory-mapped by default
bayestar = BayestarQuery(version='bayestar2019')
reddening = bayestar(coords, mode='best')
"""
)

map_query_API["http"] = _console(
    """
curl -s https://argonaut.skymaps.info/api/v2/bayestar2019/query \\
     -H 'Content-Type: application/json' \\
     -d '{"l": 150.0, "b": 20.0, "d": 1.0, "mode": "best"}'
"""
)

map_query_API["maps"] = _console(
    """
curl -s https://argonaut.skymaps.info/api/v2/maps | python -m json.tool
"""
)

fetch_example = _console(
    """
# Download the maps that this service serves (several tens of GB)
python scripts/fetch_maps.py --all
"""
)

h5_open_example = _python(
    """
import h5py

with h5py.File('bayestar2019.h5', 'r') as f:
    print(list(f.keys()))
    print(f['samples'].shape)      # (n_pixels, n_samples, n_distances)
    print(f['best_fit'].shape)     # (n_pixels, n_distances)
    print(f['pixel_info'].dtype)
"""
)

reindex_example = [
    _python(
        """
import h5py
import numpy as np

with h5py.File('bayestar2019.h5', 'r') as f:
    pix_info = f['pixel_info'][:]
    # Median reddening in the farthest distance bin, converted to E(g−r)
    far_median = 0.901 * np.median(f['samples'][:, :, -1], axis=1)
"""
    ),
    _python(
        """
import healpy as hp

nside_max = int(pix_info['nside'].max())
n_pix = hp.nside2npix(nside_max)
pix_val = np.full(n_pix, np.nan, dtype='f4')
"""
    ),
    _python(
        """
for nside in np.unique(pix_info['nside']):
    idx = (pix_info['nside'] == nside)
    nside_int = int(nside)

    # Nested pixel indices at this resolution (cast: the file stores uint64)
    hp_idx = pix_info['healpix_index'][idx].astype('i8')

    # Each coarse pixel maps to (nside_max / nside)^2 fine pixels
    factor = (nside_max // nside_int) ** 2
    fine_idx = np.repeat(hp_idx * factor, factor)
    fine_idx += np.tile(np.arange(factor), hp_idx.size)

    pix_val[fine_idx] = np.repeat(far_median[idx], factor)
"""
    ),
    _python(
        """
import matplotlib.pyplot as plt

hp.mollview(pix_val, nest=True, title='E(B−V) in the farthest bin')
plt.show()
"""
    ),
]


# Convenience aliases for templates
python = map_query_API["python"]
http = map_query_API["http"]
local = map_query_API["local"]
maps_api = map_query_API["maps"]
