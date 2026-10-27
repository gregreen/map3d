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


def test_every_map_declares_a_schema(registry):
    for name in registry.names():
        spec = registry.spec(name)
        assert isinstance(spec.schema, dict), name
        assert set(spec.schema) <= {
            "mode",
            "pct",
            "return_flags",
            "seed_or_rng",
            "order",
        }, name


def test_probabilistic_maps_accept_a_seed(registry):
    for name in ("bayestar2015", "bayestar2017", "bayestar2019", "decaps", "edenhofer2023"):
        assert "seed_or_rng" in registry.spec(name).schema, name
    for name in ("sfd", "csfd", "planck-ebv", "planck-gnilc"):
        assert "seed_or_rng" not in registry.spec(name).schema, name


def test_schemas_agree_with_capabilities(registry):
    for name, spec in registry.specs.items():
        assert ("return_flags" in spec.schema) == spec.supports_flags, name
        assert ("mode" in spec.schema) == bool(spec.modes), name
        assert ("order" in spec.schema) == (not spec.is_3d and name == "sfd"), name


def test_schema_of_each_2d_map():
    registry = build_registry({"MAX_SAMPLES": 5})
    assert set(registry.spec("sfd").schema) == {"order"}
    assert set(registry.spec("csfd").schema) == {"return_flags"}
    for name in ("planck-tau353", "planck-radiance", "planck-ebv", "planck-gnilc"):
        assert registry.spec(name).schema == {}


def _make_spec(**overrides):
    values = {
        "name": "x",
        "description": "",
        "citation": "",
        "kind": "2d",
        "factory": lambda: None,
        "schema": {},
    }
    values.update(overrides)
    return MapSpec(**values)


def test_schema_must_be_a_dict():
    with pytest.raises(TypeError, match="schema must be a dict"):
        _make_spec(schema=None)


def test_schema_cannot_declare_unknown_arguments():
    with pytest.raises(ValueError, match="unsupported argument"):
        _make_spec(schema={"nope": {"type": "string"}})


def test_schema_return_flags_must_match_supports_flags():
    with pytest.raises(ValueError, match="must agree"):
        _make_spec(schema={"return_flags": {"type": "boolean"}})


def test_schema_pct_requires_mode():
    with pytest.raises(ValueError, match="requires 'mode'"):
        _make_spec(schema={"pct": {"type": "numberlike_ndarray"}})


def test_schema_modes_must_match_declared_modes():
    schema = {"mode": {"type": "string", "default": "mean", "allowed": ["mean", "best"]}}
    with pytest.raises(ValueError, match="must agree"):
        _make_spec(kind="3d", schema=schema, modes=("mean",), default_mode="mean")


def test_schema_order_rejected_on_3d_map():
    with pytest.raises(ValueError, match="2D interpolation"):
        _make_spec(kind="3d", schema={"order": {"type": "integer"}}, supports_flags=False)


def test_schema_seed_requires_samples():
    with pytest.raises(ValueError, match="must store samples"):
        _make_spec(kind="3d", schema={"seed_or_rng": {"type": "integer", "min": 0}})


def test_schema_seed_accepted_with_samples():
    spec = _make_spec(
        kind="3d", schema={"seed_or_rng": {"type": "integer", "min": 0}}, supports_samples=True
    )
    assert "seed_or_rng" in spec.schema


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
        schema={},
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
        schema={},
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
