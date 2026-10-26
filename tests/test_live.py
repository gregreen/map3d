"""Opt-in checks against a running deployment.

    MAP3D_LIVE_API=https://argonaut.skymaps.info/api/v2/ pytest -m live

Run them explicitly: the default test command deselects them.
"""

from __future__ import annotations

import json
import os
import urllib.request

import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

pytestmark = pytest.mark.live

API = os.environ.get("MAP3D_LIVE_API", "http://127.0.0.1:5000/api/v2/")

requires_api = pytest.mark.skipif(
    not os.environ.get("MAP3D_LIVE_API"),
    reason="set MAP3D_LIVE_API to the deployment's /api/v2/",
)


def test_maps_endpoint_lists_3d_maps():
    with urllib.request.urlopen(API.rstrip("/") + "/maps", timeout=30) as response:
        payload = json.load(response)
    names = set(payload["maps"])
    assert {"bayestar2019", "decaps", "edenhofer2023"} <= names


@requires_api
def test_bayestar_web_query_roundtrip():
    from dustmaps.bayestar import BayestarWebQuery

    query = BayestarWebQuery(api_url=API, version="bayestar2019")
    coords = SkyCoord(
        [120.0, 150.0] * u.deg, [10.0, -5.0] * u.deg, frame="galactic"
    )
    values = query(coords, mode="mean")
    assert values.shape[0] == 2
    assert values.shape[1] > 10
    assert (values >= 0).all()

    samples, flags = query(coords, mode="samples", return_flags=True)
    assert samples.shape[0] == 2 and samples.shape[1] <= 5
    assert flags["converged"].shape == (2,)


@requires_api
def test_sfd_web_query():
    from dustmaps.sfd import SFDWebQuery

    query = SFDWebQuery(api_url=API)
    values = query(SkyCoord([10.0, 20.0] * u.deg, [0.0, 5.0] * u.deg, frame="galactic"))
    assert values.shape == (2,)
    assert (values > 0).all()


@requires_api
def test_interactive_endpoint():
    url = (
        API.rstrip("/").replace("/api/v2", "")
        + "/api/v2/interactive/bayestar2019/losdata?lon=120&lat=10&coordsys=gal"
    )
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = json.load(response)
    assert payload["map"] == "bayestar2019"
    assert len(payload["best"]) == len(payload["distmod"])
    assert payload["units"] == "E(g−r)"
