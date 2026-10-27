"""Test fixtures: tiny synthetic maps, so no downloads are needed."""

from __future__ import annotations

import functools
import json

import healpy as hp
import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import SkyCoord
from dustmaps.bayestar import BayestarQuery
from test_fixtures import (
    Fake2DQuery,
    Fake3DDistanceSamples,
    FakeFootprintQuery,
    make_bayestar_h5,
)

from map3d import create_app
from map3d.maps import MapRegistry, build_registry
from map3d.postage_stamp import StampImageStore

TWO_D_MAPS = (
    "sfd",
    "csfd",
    "planck-tau353",
    "planck-radiance",
    "planck-ebv",
    "planck-gnilc",
)


@pytest.fixture(scope="session")
def bayestar_h5(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "bayestar2019_test.h5"
    make_bayestar_h5(path, nside=8, n_samples=3)
    return path


def _replace(spec, **changes):
    values = {field: getattr(spec, field) for field in spec.__dataclass_fields__}
    values.update(changes)
    return spec.__class__(**values)


def _registry(config, h5_path) -> MapRegistry:
    base = build_registry(config)
    specs = []
    for spec in base.specs.values():
        if spec.name in ("bayestar2019", "bayestar2015"):
            specs.append(
                _replace(
                    spec,
                    factory=functools.partial(
                        BayestarQuery,
                        map_fname=str(h5_path),
                        max_samples=3,
                        memmap=True,
                    ),
                )
            )
        elif spec.name in TWO_D_MAPS:
            specs.append(
                _replace(spec, factory=functools.partial(Fake2DQuery, spec.name))
            )
        elif spec.name == "edenhofer2023":
            specs.append(_replace(spec, factory=Fake3DDistanceSamples))
        elif spec.name in ("decaps",):
            specs.append(_replace(spec, factory=FakeFootprintQuery))
        else:
            specs.append(spec)
    return MapRegistry(specs)


@pytest.fixture
def app_factory(tmp_path, bayestar_h5):
    """Build apps with different configuration (e.g. proxy handling)."""
    images_dir = tmp_path / "images"
    store = StampImageStore(images_dir)
    nside = 8
    n_pix = hp.nside2npix(nside)
    pixval = np.linspace(0.0, 1.0, n_pix * 3).reshape(n_pix, 3).astype("f4")
    store.save("bayestar2019", nside, pixval, [300.0, 1000.0, 5000.0])
    store.save("bayestar2015", nside, pixval, [300.0, 1000.0, 5000.0])

    base_config = {
        "TESTING": True,
        "STATE_DIR": str(tmp_path),
        "SQLITE_PATH": str(tmp_path / "map3d.sqlite3"),
        "IMAGES_DIR": str(images_dir),
        "GEOIP_ENABLED": False,
        "USAGE_STATS_ENABLED": True,
        "TRUSTED_PROXY_HOPS": 0,
        "MAX_SAMPLES": 3,
        "LOG_LEVEL": "WARNING",
        "RATE_LIMIT_API_REQUESTS": 1000,
        "RATE_LIMIT_API_WORK": 10_000_000,
        "RATE_LIMIT_INTERACTIVE_REQUESTS": 1000,
        "RATE_LIMIT_INTERACTIVE_WORK": 10_000_000,
    }
    base_config["REGISTRY"] = _registry(base_config, bayestar_h5)

    def factory(**overrides):
        config = dict(base_config)
        config.update(overrides)
        return create_app(config)

    return factory


@pytest.fixture
def app(app_factory):
    return app_factory()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def services(app):
    return app.extensions["map3d"]


@pytest.fixture
def encode():
    from dustmaps import json_serializers

    def _encode(obj):
        return json.dumps(obj, cls=json_serializers.get_encoder(ndarray_mode="b64"))

    return _encode


@pytest.fixture
def decode():
    from dustmaps import json_serializers

    def _decode(raw):
        return json.loads(raw, cls=json_serializers.MultiJSONDecoder)

    return _decode


@pytest.fixture
def coords():
    return SkyCoord(120.0 * u.deg, 10.0 * u.deg, frame="galactic")
