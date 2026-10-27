"""Registry, capability metadata and size-estimation tests."""

from __future__ import annotations

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord

from map3d.maps import (
    MapRegistry,
    MapSpec,
    build_registry,
    coords_have_distance,
    curve_distances,
    distance_moduli,
    n_coords,
    output_size,
)

EXPECTED = {
    "bayestar2015",
    "bayestar2017",
    "bayestar2019",
    "decaps",
    "edenhofer2023",
    "sfd",
    "csfd",
    "planck-tau353",
    "planck-radiance",
    "planck-ebv",
    "planck-gnilc",
}


@pytest.fixture
def registry():
    return build_registry({"MAX_SAMPLES": 5})


def test_registry_has_all_required_maps(registry):
    assert set(registry.names()) == EXPECTED


def test_registry_does_not_open_any_map(registry):
    # Maps are constructed lazily, after the worker forks.
    assert registry.loaded() == []


def test_3d_maps_declare_stamps_and_modes(registry):
    for name in ("bayestar2015", "bayestar2017", "bayestar2019", "decaps", "edenhofer2023"):
        spec = registry.spec(name)
        assert spec.is_3d
        assert spec.stamp_distances and len(spec.stamp_distances) == 3
        assert spec.modes


def test_2d_maps_have_no_stamps(registry):
    for name in ("sfd", "csfd", "planck-tau353", "planck-radiance", "planck-ebv", "planck-gnilc"):
        spec = registry.spec(name)
        assert not spec.is_3d
        assert spec.stamp_distances is None
        assert spec.supports_distance is False


def test_planck_alias(registry):
    assert registry.resolve("planck").name == "planck-ebv"
    assert "planck" in registry
    assert registry.resolve("nope") is None


def test_duplicate_names_rejected(registry):
    spec = registry.spec("sfd")
    with pytest.raises(ValueError):
        MapRegistry([spec, spec])


def test_alias_collision_rejected(registry):
    spec = MapSpec(
        name="x",
        description="",
        citation="",
        kind="2d",
        factory=lambda: None,
        aliases=("sfd",),
    )
    with pytest.raises(ValueError):
        MapRegistry([registry.spec("sfd"), spec])


def test_enabled_maps_filter():
    subset = build_registry({"MAX_SAMPLES": 5, "ENABLED_MAPS": ["bayestar2019", "sfd"]})
    assert subset.names() == ["bayestar2019", "sfd"]


def test_unknown_enabled_map_rejected():
    with pytest.raises(ValueError):
        build_registry({"MAX_SAMPLES": 5, "ENABLED_MAPS": ["nope"]})


def test_public_metadata_capabilities(registry):
    meta = registry.public_metadata()
    assert meta["edenhofer2023"]["requires_distance"] is True
    assert meta["bayestar2019"]["supports_samples"] is True
    assert meta["sfd"]["supports_distance"] is False
    assert meta["bayestar2019"]["units"].startswith("Bayestar reddening")
    assert meta["bayestar2019"]["display_units"] == "E(g−r)"
    assert meta["bayestar2019"]["display_scale"] == 0.901
    assert meta["decaps"]["display_units"] == "E(B−V)"
    # Partial-coverage maps name their footprint; full-sky maps do not
    assert meta["decaps"]["no_coverage_warning"] == (
        "This sightline is outside the DECaPS footprint."
    )
    for name in ("bayestar2015", "bayestar2017", "bayestar2019"):
        assert meta[name]["no_coverage_warning"] == (
            "This sightline is outside the Bayestar footprint."
        )
    assert meta["edenhofer2023"]["no_coverage_warning"] == ""
    assert "did not converge" in meta["bayestar2019"]["warning"]
    assert meta["edenhofer2023"]["display_units"] == "E(440 nm − 550 nm)"
    assert meta["edenhofer2023"]["display_scale"] == pytest.approx(0.9663921356201177)


def test_output_size_scalar_and_samples():
    class FakeQuery:
        _n_samples = 4
        _n_distances = 10

    spec = MapSpec(
        name="f",
        description="",
        citation="",
        kind="3d",
        factory=lambda: None,
        size_kind="probabilistic",
        default_mode="mean",
    )
    q = FakeQuery()
    coords = SkyCoord([1.0, 2.0] * u.deg, [0.0, 0.0] * u.deg, frame="galactic")
    assert n_coords(coords) == 2
    assert not coords_have_distance(coords)

    assert output_size(q, spec, coords, {"mode": "mean"}) == 2 * 1 * 10
    assert output_size(q, spec, coords, {"mode": "samples"}) == 2 * 4 * 10
    assert output_size(q, spec, coords, {"mode": "percentile", "pct": [1.0, 50.0]}) == 2 * 2 * 10

    coords3d = SkyCoord(
        [1.0, 2.0] * u.deg, [0.0, 0.0] * u.deg, distance=[1.0, 2.0] * u.kpc, frame="galactic"
    )
    assert coords_have_distance(coords3d)
    assert output_size(q, spec, coords3d, {"mode": "samples"}) == 2 * 4


def test_distance_moduli_from_distances_quantity():
    class FakeEdenhofer:
        distances = np.array([100.0, 1000.0]) * u.pc

    dm = distance_moduli(FakeEdenhofer())
    np.testing.assert_allclose(dm, 5.0 * np.log10(np.array([100.0, 1000.0]) / 10.0))


def test_curve_distances_subsamples_long_axes():
    class Dense:
        distances = np.linspace(68.0, 1244.0, 516) * u.pc

    curve = curve_distances(Dense(), n_points=64)
    assert curve.size == 64
    assert curve.min() < curve.max()
