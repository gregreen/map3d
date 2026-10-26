"""Tests for the public query API."""

from __future__ import annotations

import json

import numpy as np
from astropy import units as u
from astropy.coordinates import SkyCoord


def test_maps_endpoint_lists_3d_and_2d(client):
    r = client.get("/api/v2/maps")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] >= 10
    maps = data["maps"]
    assert maps["bayestar2019"]["kind"] == "3d"
    assert maps["bayestar2019"]["supports_samples"] is True
    assert maps["edenhofer2023"]["requires_distance"] is True
    assert maps["sfd"]["kind"] == "2d"
    assert maps["planck-ebv"]["kind"] == "2d"


def test_query_best_mode_roundtrips_through_dustmaps_decoder(client, decode):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 120.0, "b": 10.0, "mode": "best"}
    )
    assert r.status_code == 200, r.data
    out = decode(r.data)
    assert isinstance(out, np.ndarray)
    assert out.shape == (5,)
    np.testing.assert_allclose(out, [0.1, 0.2, 0.3, 0.4, 0.5], rtol=1e-6)


def test_query_mean_matches_direct_map_call(client, decode, services):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 120.0, "b": 10.0, "mode": "mean"}
    )
    assert r.status_code == 200
    out = decode(r.data)

    query_obj = services.registry.get("bayestar2019")
    direct = query_obj(SkyCoord(120.0 * u.deg, 10.0 * u.deg, frame="galactic"), mode="mean")
    np.testing.assert_allclose(out, direct, rtol=1e-6)


def test_query_samples_mode_shape(client, decode):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 120.0, "b": 10.0, "mode": "samples"}
    )
    assert r.status_code == 200
    out = decode(r.data)
    assert out.shape == (3, 5)


def test_query_single_distance(client, decode):
    r = client.post(
        "/api/v2/bayestar2019/query",
        json={"l": 120.0, "b": 10.0, "d": 1.0, "mode": "best"},
    )
    assert r.status_code == 200
    out = decode(r.data)
    assert np.size(out) == 1
    assert np.all(np.isfinite(out))


def test_query_percentile(client, decode):
    r = client.post(
        "/api/v2/bayestar2019/query",
        json={"l": 120.0, "b": 10.0, "mode": "percentile", "pct": [15.8, 50.0, 84.2]},
    )
    assert r.status_code == 200
    out = decode(r.data)
    assert out.size == 15


def test_query_percentile_requires_pct(client):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 120.0, "b": 10.0, "mode": "percentile"}
    )
    assert r.status_code == 400
    assert "pct" in json.dumps(r.get_json())


def test_query_return_flags(client, decode):
    r = client.post(
        "/api/v2/bayestar2019/query",
        json={"l": 120.0, "b": 10.0, "mode": "samples", "return_flags": True},
    )
    assert r.status_code == 200
    out = decode(r.data)
    assert len(out) == 2
    assert np.asarray(out[0]).shape == (3, 5)
    assert bool(out[1]["converged"]) is True


def test_query_skycoord_body(client, decode, encode):
    coords = SkyCoord(
        [120.0, 121.0] * u.deg, [10.0, 11.0] * u.deg, frame="galactic"
    )
    body = encode({"coords": coords, "mode": "best"})
    r = client.post(
        "/api/v2/bayestar2019/query", data=body, content_type="application/json"
    )
    assert r.status_code == 200, r.data
    out = decode(r.data)
    assert out.shape == (2, 5)


def test_query_2d_map(client, decode):
    r = client.post("/api/v2/sfd/query", json={"l": 120.0, "b": 10.0})
    assert r.status_code == 200
    out = decode(r.data)
    assert np.allclose(out, 0.12)


def test_query_2d_map_rejects_distance(client):
    r = client.post("/api/v2/sfd/query", json={"l": 120.0, "b": 10.0, "d": 1.0})
    assert r.status_code == 400
    assert "2D" in r.get_json()["error"]


def test_query_map_requiring_distance(client):
    r = client.post("/api/v2/edenhofer2023/query", json={"l": 120.0, "b": 10.0})
    assert r.status_code == 400
    assert "distance" in r.get_json()["error"]


def test_query_edenhofer_with_distance(client, decode):
    r = client.post(
        "/api/v2/edenhofer2023/query",
        json={"l": 120.0, "b": 10.0, "d": 0.5, "mode": "mean"},
    )
    assert r.status_code == 200
    out = decode(r.data)
    assert np.allclose(out, 5e-4 * 500.0)


def test_query_edenhofer_samples(client, decode):
    r = client.post(
        "/api/v2/edenhofer2023/query",
        json={"l": 120.0, "b": 10.0, "d": 0.5, "mode": "samples"},
    )
    assert r.status_code == 200, r.data
    out = decode(r.data)
    # one row for the requested coordinate, one column per stored sample
    assert np.shape(out) == (1, 4)
    assert np.allclose(np.mean(out), 5e-4 * 500.0, rtol=0.2)


def test_invalid_map_name(client):
    r = client.post("/api/v2/not-a-map/query", json={"l": 1.0, "b": 1.0})
    assert r.status_code == 400
    assert "not-a-map" in r.get_json()["error"]


def test_invalid_mode(client):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 1.0, "b": 1.0, "mode": "nonsense"}
    )
    assert r.status_code == 400
    assert "input_errors" in r.get_json()


def test_unknown_keyword_argument(client):
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 1.0, "b": 1.0, "frobnicate": 2}
    )
    assert r.status_code == 400
    assert "frobnicate" in json.dumps(r.get_json())


def test_bad_json_body(client):
    r = client.post(
        "/api/v2/bayestar2019/query", data="{not json", content_type="application/json"
    )
    assert r.status_code == 400
    assert "JSON" in r.get_json()["input_errors"]["body"][0]


def test_empty_body(client):
    r = client.post("/api/v2/bayestar2019/query", data=b"", content_type="application/json")
    assert r.status_code == 400


def test_missing_coordinates(client):
    r = client.post("/api/v2/bayestar2019/query", json={"mode": "best"})
    assert r.status_code == 400


def test_latitude_out_of_range(client):
    r = client.post("/api/v2/bayestar2019/query", json={"l": 10.0, "b": 120.0})
    assert r.status_code == 400


def test_wrong_method(client):
    r = client.get("/api/v2/bayestar2019/query")
    assert r.status_code == 405


def test_oversized_output_rejected(client, app):
    app.config["MAX_OUTPUT_VALUES"] = 10
    r = client.post(
        "/api/v2/bayestar2019/query", json={"l": 120.0, "b": 10.0, "mode": "samples"}
    )
    assert r.status_code == 413
    payload = r.get_json()
    assert payload["max_size"] == 10


def test_too_many_coordinates(client, app):
    app.config["MAX_COORDS"] = 2
    r = client.post(
        "/api/v2/bayestar2019/query",
        json={"l": [1.0, 2.0, 3.0], "b": [1.0, 2.0, 3.0], "mode": "best"},
    )
    assert r.status_code == 413


def test_rate_limit_headers_on_success(client):
    r = client.post("/api/v2/sfd/query", json={"l": 1.0, "b": 1.0})
    assert r.status_code == 200
    assert int(r.headers["X-RateLimit-Limit"]) > 0
    assert "X-RateLimit-Remaining" in r.headers
    assert r.headers["X-Request-ID"]


def test_stats_endpoint(client):
    client.post("/api/v2/sfd/query", json={"l": 1.0, "b": 1.0})
    r = client.get("/api/v2/stats?days=1")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["window_days"] == 1
    assert any(entry["map"] == "sfd" for entry in payload["maps"])
    assert "no client identifiers" in payload["note"]


def test_openapi_and_health(client):
    assert client.get("/api/v2/openapi.json").status_code == 200
    health = client.get("/healthz").get_json()
    assert health["status"] == "ok"
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.get_json()["status"] == "ready"


def test_gzip_negotiation(client):
    body = json.dumps({"l": [float(x) for x in range(50)], "b": [1.0] * 50, "mode": "best"})
    r = client.post(
        "/api/v2/bayestar2019/query",
        data=body,
        content_type="application/json",
        headers={"Accept-Encoding": "gzip"},
    )
    assert r.status_code == 200
    assert r.headers.get("Content-Encoding") == "gzip"


def test_security_headers(client):
    r = client.get("/healthz")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Referrer-Policy"]
