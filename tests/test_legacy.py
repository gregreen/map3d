"""The deprecated v1 endpoints must keep working, with deprecation headers."""

from __future__ import annotations

import numpy as np


def test_light_full_mode(client):
    r = client.post(
        "/gal-lb-query-light",
        json={"l": [120.0, 121.0], "b": [10.0, 11.0], "mode": "full"},
    )
    assert r.status_code == 200, r.data
    payload = r.get_json()
    assert set(["samples", "best", "distmod", "converged"]).issubset(payload)
    assert np.asarray(payload["samples"]).shape == (2, 3, 5)
    assert np.asarray(payload["best"]).shape == (2, 5)
    assert payload["distmod"] == [4.0, 6.0, 8.0, 10.0, 12.0]

    assert r.headers["Deprecation"] == "true"
    assert "deprecated" in r.headers["Warning"].lower()


def test_light_lite_mode(client):
    r = client.post(
        "/gal-lb-query-light", json={"l": 120.0, "b": 10.0, "mode": "lite"}
    )
    assert r.status_code == 200
    payload = r.get_json()
    assert "median" in payload and "sigma" in payload and "best" in payload
    assert np.asarray(payload["sigma"]).shape == (5,)
    assert np.all(np.asarray(payload["sigma"]) >= 0)


def test_light_sfd_mode(client):
    r = client.post("/gal-lb-query-light", json={"l": 120.0, "b": 10.0, "mode": "sfd"})
    assert r.status_code == 200
    assert np.allclose(r.get_json()["EBV_SFD"], 0.12)


def test_light_too_many_coords(client):
    n = 6000
    r = client.post(
        "/gal-lb-query-light",
        json={"l": [1.0] * n, "b": [1.0] * n, "mode": "full"},
    )
    assert r.status_code == 413


def test_light_rejects_unknown_mode(client):
    r = client.post("/gal-lb-query-light", json={"l": 1.0, "b": 1.0, "mode": "bogus"})
    assert r.status_code == 400


def test_gal_lb_query(client):
    r = client.get("/gal-lb-query?lon=120&lat=10&coordsys=gal")
    assert r.status_code == 200, r.data
    payload = r.get_json()
    assert payload["success"] is True
    assert "table" in payload
    assert payload["radius"] == 7.5
    assert np.asarray(payload["samples"]).shape == (3, 5)
    assert r.headers["Deprecation"] == "true"
