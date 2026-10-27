"""Tests for the interactive-page endpoints."""

from __future__ import annotations

import numpy as np
import pytest


def test_losdata_for_map_with_samples(client):
    r = client.get(
        "/api/v2/interactive/bayestar2019/losdata?lon=120&lat=10&coordsys=gal"
    )
    assert r.status_code == 200, r.data
    data = r.get_json()

    assert data["map"] == "bayestar2019"
    # Bayestar is reported in SFD-like units; the page plots E(g−r)
    assert data["units"] == "E(g−r)"
    assert data["has_samples"] is True
    assert len(data["distmod"]) == 5
    assert len(data["best"]) == 5
    assert np.asarray(data["samples"]).shape == (3, 5)

    # E(g−r) = 0.901 x (Bayestar reddening), Green et al. (2019) Eq. 30
    np.testing.assert_allclose(
        data["best"], np.array([0.1, 0.2, 0.3, 0.4, 0.5]) * 0.901, rtol=1e-6
    )
    assert data["converged"] is True
    assert data["success"] is True
    assert data["radius"] == 7.5
    # No warning for a sightline the map is happy with
    assert data["warning"] is None
    assert data["infilled"] is None


def test_losdata_includes_postage_stamps(client):
    r = client.get(
        "/api/v2/interactive/bayestar2019/losdata?lon=120&lat=10&coordsys=gal"
    )
    data = r.get_json()
    assert data["images_available"] is True
    for k in (1, 2, 3):
        assert data[f"image{k}"].startswith("data:image/jpeg;base64,")
    assert data["label1"] == "300 pc"
    assert data["label3"] == "5000 pc"


def test_losdata_without_images(client):
    r = client.get("/api/v2/interactive/bayestar2015/losdata?lon=10&lat=10&coordsys=gal")
    assert r.status_code == 200
    data = r.get_json()
    assert data["images_available"] is True  # fixture provides images for 2015 too


def test_losdata_equatorial_coordinates(client):
    r = client.get(
        "/api/v2/interactive/bayestar2019/losdata?lon=200&lat=20&coordsys=equ"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert -180.0 <= data["l"] <= 360.0
    assert -90.0 <= data["b"] <= 90.0


def test_losdata_rejects_2d_map(client):
    r = client.get("/api/v2/interactive/sfd/losdata?lon=10&lat=10&coordsys=gal")
    assert r.status_code == 400
    assert "2D" in r.get_json()["error"]


def test_losdata_unknown_map(client):
    r = client.get("/api/v2/interactive/nope/losdata?lon=10&lat=10&coordsys=gal")
    assert r.status_code == 400


def test_losdata_bad_latitude(client):
    r = client.get(
        "/api/v2/interactive/bayestar2019/losdata?lon=10&lat=200&coordsys=gal"
    )
    assert r.status_code == 400


def test_losdata_missing_parameters(client):
    assert client.get("/api/v2/interactive/bayestar2019/losdata").status_code == 400


def test_losdata_map_queried_distance_by_distance(client):
    r = client.get(
        "/api/v2/interactive/edenhofer2023/losdata?lon=120&lat=10&coordsys=gal"
    )
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert data["has_samples"] is True
    assert data["converged"] is None
    assert data["min_reliable_distmod"] is None
    # maps with few native distance bins use them as-is (here: 24 radii)
    assert len(data["best"]) == 24
    # one row per posterior sample, one column per distance
    assert len(data["samples"]) == 4
    assert all(len(row) == len(data["best"]) for row in data["samples"])


def test_losdata_outside_footprint_explains_itself(client):
    # The fake DECaPS has no data beyond l = 128 deg: that must not be reported
    # as a failed fit, which is what Bayestar's wording would say.
    r = client.get(
        "/api/v2/interactive/decaps/losdata?lon=200&lat=10&coordsys=gal"
    )
    assert r.status_code == 200, r.data
    data = r.get_json()
    assert data["converged"] is False
    assert data["infilled"] is False
    assert data["success"] is False
    # The page hatches the whole plot and says so, rather than "unreliable"
    assert data["in_footprint"] is False
    assert data["warning"] == "This sightline is outside the DECaPS footprint."


def test_losdata_infilled_pixel_says_so(client):
    r = client.get(
        "/api/v2/interactive/decaps/losdata?lon=126.5&lat=10&coordsys=gal"
    )
    data = r.get_json()
    assert data["converged"] is False
    assert data["infilled"] is True
    assert "infilled" in data["warning"]
    # The pixel does have values, so this is not the out-of-footprint case
    assert data["success"] is True
    assert data["in_footprint"] is True


def test_losdata_inside_footprint_has_no_warning(client):
    r = client.get(
        "/api/v2/interactive/decaps/losdata?lon=120&lat=10&coordsys=gal"
    )
    data = r.get_json()
    assert data["converged"] is True
    assert data["in_footprint"] is True
    assert data["warning"] is None


@pytest.mark.parametrize(
    "map_name,best,converged,infilled,expected",
    [
        # covered and converged: nothing to say
        ("bayestar2019", [0.1, 0.2], True, None, None),
        # covered, fit failed: the convergence caution
        ("bayestar2019", [0.0, 0.0], False, None,
         "The line-of-sight fit did not converge in this direction; "
         "treat the values with caution."),
        # no data at all: outside the footprint, which is a different problem
        ("bayestar2019", [np.nan, np.nan], False, None,
         "This sightline is outside the Bayestar footprint."),
        ("bayestar2015", [np.nan, np.nan], False, None,
         "This sightline is outside the Bayestar footprint."),
        ("bayestar2017", [np.nan, np.nan], False, None,
         "This sightline is outside the Bayestar footprint."),
        ("decaps", [np.nan, np.nan], False, False,
         "This sightline is outside the DECaPS footprint."),
        # infilled from the neighbors, which DECaPS reports as not converged
        ("decaps", [0.1, 0.2], False, True,
         "This sightline was infilled from neighboring pixels; "
         "treat the values with caution."),
        # a map with full-sky coverage has no footprint message to offer
        ("edenhofer2023", [np.nan], None, None, None),
    ],
)
def test_warning_wording_per_map(services, map_name, best, converged, infilled, expected):
    from map3d.views.interactive import _warning_for

    spec = services.registry.spec(map_name)
    assert _warning_for(spec, np.asarray(best, dtype="f8"), converged, infilled) == expected


def test_lostable_returns_plain_text(client):
    r = client.get(
        "/api/v2/interactive/bayestar2019/lostable?lon=120&lat=10&coordsys=gal"
    )
    assert r.status_code == 200
    assert r.mimetype == "text/plain"
    body = r.data.decode("utf-8")
    assert "Line-of-Sight Reddening Results" in body
    assert "BestFit" in body
    assert "E(g\u2212r)" in body
    assert r.headers["Content-Type"].endswith("charset=utf-8")
    assert "bayestar2019_l_120.0000_b_10.0000.txt" in r.headers["Content-Disposition"]


def test_lostable_without_flags(client):
    r = client.get(
        "/api/v2/interactive/edenhofer2023/lostable?lon=120&lat=10&coordsys=gal"
    )
    assert r.status_code == 200
    assert "not reported by this map" in r.data.decode("utf-8")
