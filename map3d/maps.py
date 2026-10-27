"""Registry of served dust maps.

Each map is described once, declaratively. The API, the interactive page, the
data fetcher and the postage-stamp image builder all read from this registry, so
adding a map is a single entry here plus a fetch.

Query objects are constructed lazily, on first use *within a worker process*.
With ``memmap=True`` they hold an open HDF5/FITS handle, and those handles must
never be created before the process forks, so nothing here touches a file at
import time.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from astropy import units as u

from .validators import to_array

log = logging.getLogger(__name__)

KIND_3D = "3d"
KIND_2D = "2d"

BAYESTAR_MODES = (
    "random_sample",
    "random_sample_per_pix",
    "samples",
    "median",
    "mean",
    "best",
    "percentile",
)

# DECaPS has no 'best' mode (the published best fit is not stored).
DECAPS_MODES = tuple(mode for mode in BAYESTAR_MODES if mode != "best")

EDENHOFER_MODES = ("mean", "std", "samples", "random_sample")

# Every keyword argument any served map accepts. A schema may only use these, so
# that a typo becomes an error at import time rather than a silently ignored
# request field.
QUERY_KWARGS = frozenset({"mode", "pct", "return_flags", "seed_or_rng", "order"})


def _mode_field(modes, default: str) -> dict:
    """Schema for ``mode``, accepting exactly the modes the map supports."""
    branches = [{"allowed": [mode for mode in modes if mode != "percentile"]}]
    if "percentile" in modes:
        branches.append({"allowed": ["percentile"], "dependencies": "pct"})
    return {"type": "string", "default": default, "anyof": branches}


def _pct_field() -> dict:
    return {
        "coerce": to_array("f8"),
        "type": "numberlike_ndarray",
        "minall": 0.0,
        "maxall": 100.0,
        "dependencies": {"mode": "percentile"},
        "nullable": True,
    }


def _return_flags_field() -> dict:
    return {"type": "boolean", "default": False}


def _not_boolean(field, value, error):
    if isinstance(value, bool):
        error(field, "must be an integer seed, not a boolean")


def _seed_field() -> dict:
    """`seed_or_rng`, restricted to an integer seed.

    ``dustmaps`` also accepts a :obj:`numpy.random.Generator` here, so that a
    caller can continue its own random stream. That has no JSON representation
    we are prepared to serialize (or to trust from a client), so the API takes
    a seed only. Omitting it, or passing ``null``, gives OS-seeded randomness.
    """
    return {
        "type": "integer",
        "min": 0,
        "nullable": True,
        "check_with": _not_boolean,
    }


# Each schema below lists *every* keyword argument the map's query object
# accepts; an empty schema means the map takes none. Anything not listed is
# rejected by the API rather than passed through to `dustmaps`.

BAYESTAR_SCHEMA = {
    "mode": _mode_field(BAYESTAR_MODES, "random_sample"),
    "pct": _pct_field(),
    "return_flags": _return_flags_field(),
    "seed_or_rng": _seed_field(),
}

DECAPS_SCHEMA = {
    "mode": _mode_field(DECAPS_MODES, "mean"),
    "pct": _pct_field(),
    "return_flags": _return_flags_field(),
    "seed_or_rng": _seed_field(),
}

EDENHOFER_SCHEMA = {
    "mode": _mode_field(EDENHOFER_MODES, "mean"),
    "seed_or_rng": _seed_field(),
}

# SFD interpolates with scipy.ndimage.map_coordinates, which supports orders 0-5.
SFD_SCHEMA = {"order": {"type": "integer", "min": 0, "max": 5}}

# CSFD stores a bit mask (LSS correction, no IRAS data, cosmology-friendly) that
# `return_flags=True` returns alongside the reddening.
CSFD_SCHEMA = {"return_flags": _return_flags_field()}

# The Planck 2014 components and GNILC take no query arguments at all: the
# component is fixed by which map was requested.
PLANCK_SCHEMA = {}


@dataclass(frozen=True)
class MapSpec:
    name: str
    description: str
    citation: str
    kind: str
    factory: Callable[[], Any]
    # Keyword arguments the map's query object accepts. Required, so that a new
    # map cannot be added without deciding what the API may forward to it.
    schema: dict
    doi: str = ""
    size_kind: str = "scalar"  # 'scalar' | 'probabilistic'
    default_mode: str = "mean"
    stamp_distances: tuple[float, ...] | None = None
    supports_samples: bool = False
    supports_flags: bool = False
    supports_distance: bool = True
    requires_distance: bool = False
    # Units of the raw map output, as returned by the query API.
    api_units: str = "E(B−V)"
    # Units used by the interactive page, and the factor applied to get there.
    # (Empty `display_units` means the display uses `api_units` unscaled.)
    display_units: str = ""
    display_scale: float = 1.0
    modes: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    deprecated: bool = False
    # Shown when the map reports that a sightline inside its footprint is
    # unusable (its fit did not converge).
    warning: str = (
        "The line-of-sight fit did not converge in this direction; "
        "treat the values with caution."
    )
    # Shown instead when the sightline has no data at all, which for a partial-
    # coverage map means it lies outside the survey footprint. Empty for maps
    # that cover the whole sky.
    no_coverage_warning: str = ""
    # Shown instead of `warning` when the map reports the pixel as infilled from
    # its neighbors, as DECaPS does for sightlines just past its survey edge.
    infilled_warning: str = ""

    def __post_init__(self) -> None:
        check_schema(self)

    @property
    def is_3d(self) -> bool:
        return self.kind == KIND_3D


def check_schema(spec: MapSpec) -> None:
    """Reject a spec whose schema disagrees with the rest of its capabilities."""
    if not isinstance(spec.schema, dict):
        raise TypeError(
            f"{spec.name}: schema must be a dict (use {{}} when the map takes no "
            f"arguments), not {type(spec.schema).__name__}"
        )

    unknown = set(spec.schema) - QUERY_KWARGS
    if unknown:
        raise ValueError(
            f"{spec.name}: schema declares unsupported argument(s) {sorted(unknown)}"
        )

    if "pct" in spec.schema:
        if "mode" not in spec.schema:
            raise ValueError(f"{spec.name}: 'pct' requires 'mode' in the schema")
        if "percentile" not in spec.modes:
            raise ValueError(f"{spec.name}: 'pct' but 'percentile' is not in modes")

    if ("return_flags" in spec.schema) != spec.supports_flags:
        raise ValueError(
            f"{spec.name}: 'return_flags' in schema={('return_flags' in spec.schema)}, "
            f"supports_flags={spec.supports_flags}; these must agree"
        )

    if "seed_or_rng" in spec.schema and not spec.supports_samples:
        raise ValueError(
            f"{spec.name}: 'seed_or_rng' only affects the random modes, so the map "
            f"must store samples"
        )

    if "mode" in spec.schema:
        if not spec.modes:
            raise ValueError(f"{spec.name}: 'mode' in schema but no modes declared")
        declared = set(spec.schema["mode"].get("allowed", ()))
        for branch in spec.schema["mode"].get("anyof", ()):
            declared.update(branch.get("allowed", ()))
        if declared != set(spec.modes):
            raise ValueError(
                f"{spec.name}: schema allows {sorted(declared)} but modes are "
                f"{sorted(spec.modes)}; they must agree"
            )
        default = spec.schema["mode"].get("default", spec.modes[0])
        if default != spec.default_mode:
            raise ValueError(
                f"{spec.name}: schema default mode {default!r} != "
                f"default_mode {spec.default_mode!r}"
            )
    elif spec.modes:
        raise ValueError(f"{spec.name}: declares modes but no 'mode' argument")

    if "order" in spec.schema and spec.is_3d:
        raise ValueError(f"{spec.name}: 'order' is a 2D interpolation argument")


# ---------------------------------------------------------------------------
# Size estimation
# ---------------------------------------------------------------------------


def n_coords(coords) -> int:
    if getattr(coords, "isscalar", False):
        return 1
    return int(np.size(coords))


def coords_have_distance(coords) -> bool:
    return hasattr(coords.distance, "kpc")


def output_size(query, spec: MapSpec, coords, args: dict) -> int:
    """Estimated number of output values, used to reject oversized requests."""
    size = _value_count(query, spec, coords, args)
    if args.get("return_flags"):
        size *= 2
    return size


def _value_count(query, spec: MapSpec, coords, args: dict) -> int:
    n = n_coords(coords)
    if spec.size_kind != "probabilistic":
        return n

    get_size = getattr(query, "get_query_size", None)
    if callable(get_size):
        allowed = {"mode", "return_flags", "pct"}
        try:
            return int(get_size(coords, **{k: v for k, v in args.items() if k in allowed}))
        except Exception:
            pass

    rec = getattr(query, "_rec", None)
    mode = args.get("mode", spec.default_mode)
    if mode == "samples":
        n_samples = int(
            getattr(query, "_n_samples", None)
            or getattr(query, "n_samples", None)
            or getattr(rec, "n_samples", None)
            or 1
        )
    elif mode == "percentile":
        pct = args.get("pct")
        n_samples = int(np.size(pct)) if pct is not None else 1
    else:
        n_samples = 1

    if coords_have_distance(coords):
        n_dists = 1
    else:
        n_dists = int(
            getattr(query, "_n_distances", None) or getattr(rec, "n_radii", None) or 1
        )

    return n * max(1, n_samples) * max(1, n_dists)


# ---------------------------------------------------------------------------
# Distance axes
# ---------------------------------------------------------------------------


def _as_value(quantity, unit):
    if quantity is None:
        return None
    if isinstance(quantity, u.Quantity):
        return np.asarray(quantity.to_value(unit))
    return np.asarray(quantity)


def distance_moduli(query) -> np.ndarray | None:
    """Distance moduli (mag) of the map's native distance bins."""
    distmods = getattr(query, "distmods", None)
    if distmods is not None:
        return _as_value(distmods, u.mag)

    distances = getattr(query, "distances", None)
    if distances is not None:
        d_pc = _as_value(distances, u.pc)
        return 5.0 * np.log10(d_pc / 10.0)

    radii = getattr(getattr(query, "_rec", None), "radii", None)
    if radii is not None:
        return 5.0 * np.log10(np.asarray(radii, dtype="f8") / 10.0)
    return None


def curve_distances(query, n_points: int = 96) -> np.ndarray:
    """Distance bins to use for a line-of-sight curve, as distance moduli.

    Maps with a modest number of bins use them as-is. Edenhofer 2023 has 516
    radial bins, which is more than the plot needs, so it is subsampled.
    """
    distmods = distance_moduli(query)
    if distmods is None:
        return np.linspace(4.0, 19.0, 31)
    if distmods.size <= n_points:
        return distmods
    return np.linspace(distmods.min(), distmods.max(), n_points)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MapRegistry:
    def __init__(self, specs: list[MapSpec]):
        self._specs: dict[str, MapSpec] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise ValueError(f"duplicate map name: {spec.name}")
            self._specs[spec.name] = spec
        self._alias: dict[str, str] = {}
        for spec in specs:
            for alias in spec.aliases:
                if alias in self._specs:
                    raise ValueError(f"alias {alias!r} shadows a map name")
                self._alias[alias] = spec.name
        self._loaded: dict[str, Any] = {}
        self._lock = threading.Lock()

    def __contains__(self, name: str) -> bool:
        return name in self._specs or name in self._alias

    def names(self) -> list[str]:
        return sorted(self._specs)

    @property
    def specs(self) -> dict[str, MapSpec]:
        return dict(self._specs)

    def resolve(self, name: str) -> MapSpec | None:
        if name in self._specs:
            return self._specs[name]
        canonical = self._alias.get(name)
        return self._specs[canonical] if canonical else None

    def spec(self, name: str) -> MapSpec:
        spec = self.resolve(name)
        if spec is None:
            raise KeyError(name)
        return spec

    def get(self, name: str):
        """Return the query object for a map, constructing it on first use."""
        spec = self.spec(name)
        query = self._loaded.get(spec.name)
        if query is not None:
            return query
        with self._lock:
            query = self._loaded.get(spec.name)
            if query is None:
                t0 = time.time()
                query = spec.factory()
                self._loaded[spec.name] = query
                log.info(
                    "map loaded name=%s seconds=%.2f", spec.name, time.time() - t0
                )
        return query

    def loaded(self) -> list[str]:
        return sorted(self._loaded)

    def public_metadata(self, include_2d: bool = True) -> dict:
        out = {}
        for name in self.names():
            spec = self._specs[name]
            if not include_2d and not spec.is_3d:
                continue
            out[name] = {
                "name": name,
                "kind": spec.kind,
                "description": spec.description,
                "citation": spec.citation,
                "doi": spec.doi,
                "units": spec.api_units,
                "display_units": spec.display_units or spec.api_units,
                "display_scale": spec.display_scale,
                "requires_distance": spec.requires_distance,
                "supports_distance": spec.supports_distance,
                "supports_samples": spec.supports_samples,
                "supports_flags": spec.supports_flags,
                "query_kwargs": sorted(spec.schema),
                "modes": list(spec.modes),
                "warning": spec.warning,
                "no_coverage_warning": spec.no_coverage_warning,
                "stamp_distances_pc": (
                    list(spec.stamp_distances) if spec.stamp_distances else None
                ),
            }
        return out


def build_registry(config) -> MapRegistry:
    max_samples = int(config.get("MAX_SAMPLES", 5))

    def bayestar(version: str):
        def factory():
            from dustmaps.bayestar import BayestarQuery

            return BayestarQuery(version=version, max_samples=max_samples, memmap=True)

        return factory

    def decaps():
        from dustmaps.decaps import DECaPSQuery

        return DECaPSQuery(max_samples=max_samples, memmap=True)

    def edenhofer2023():
        from dustmaps.edenhofer2023 import Edenhofer2023Query

        # The samples are what the posterior band on the query page is drawn
        # from; `integrated=True` gives the cumulative extinction that this
        # service reports, and the map is memory-mapped either way, so the
        # 20 GB file costs nothing in resident memory.
        return Edenhofer2023Query(load_samples=True, integrated=True, memmap=True)

    def sfd():
        from dustmaps.sfd import SFDQuery

        return SFDQuery()

    def csfd():
        from dustmaps.csfd import CSFDQuery

        return CSFDQuery()

    def planck(component: str):
        def factory():
            from dustmaps.planck import PlanckQuery

            return PlanckQuery(component=component)

        return factory

    def planck_gnilc():
        from dustmaps.planck import PlanckGNILCQuery

        return PlanckGNILCQuery()

    specs = [
        MapSpec(
            name="bayestar2015",
            description="Bayestar 2015: A 3D dust map based on Pan-STARRS 1 and 2MASS.",
            citation="Green et al. (2015)",
            doi="https://doi.org/10.1088/0004-637X/810/1/25",
            kind=KIND_3D,
            factory=bayestar("bayestar2015"),
            schema=BAYESTAR_SCHEMA,
            size_kind="probabilistic",
            default_mode="random_sample",
            stamp_distances=(300.0, 1000.0, 5000.0),
            supports_samples=True,
            supports_flags=True,
            api_units="Bayestar reddening (arbitrary units)",
            display_units="E(g−r)",
            display_scale=0.901,
            modes=BAYESTAR_MODES,
            no_coverage_warning="This sightline is outside the Bayestar footprint.",
        ),
        MapSpec(
            name="bayestar2017",
            description=(
                "Bayestar 2017: An improved 3D dust map based on Pan-STARRS 1 and 2MASS."
            ),
            citation="Green et al. (2018)",
            doi="https://doi.org/10.3847/1538-4357/aab9ab",
            kind=KIND_3D,
            factory=bayestar("bayestar2017"),
            schema=BAYESTAR_SCHEMA,
            size_kind="probabilistic",
            default_mode="random_sample",
            stamp_distances=(300.0, 1000.0, 5000.0),
            supports_samples=True,
            supports_flags=True,
            api_units="Bayestar reddening (arbitrary units)",
            display_units="E(g−r)",
            display_scale=0.901,
            modes=BAYESTAR_MODES,
            no_coverage_warning="This sightline is outside the Bayestar footprint.",
        ),
        MapSpec(
            name="bayestar2019",
            description=(
                "Bayestar 2019: A 3D dust map based on Pan-STARRS 1, 2MASS and "
                "Gaia DR2."
            ),
            citation="Green et al. (2019)",
            doi="https://doi.org/10.3847/1538-4357/ab5362",
            kind=KIND_3D,
            factory=bayestar("bayestar2019"),
            schema=BAYESTAR_SCHEMA,
            size_kind="probabilistic",
            default_mode="random_sample",
            stamp_distances=(300.0, 1000.0, 5000.0),
            supports_samples=True,
            supports_flags=True,
            api_units="Bayestar reddening (arbitrary units)",
            display_units="E(g−r)",
            display_scale=0.901,
            modes=BAYESTAR_MODES,
            no_coverage_warning="This sightline is outside the Bayestar footprint.",
        ),
        MapSpec(
            name="decaps",
            description=(
                "DECaPS: A 3D dust map of the southern Galactic plane based on the DECaPS2 "
                "survey, 2MASS, VVV, unWISE and Gaia DR3."
            ),
            citation="Zucker et al. (2025)",
            doi="https://doi.org/10.3847/1538-4357/ada252",
            kind=KIND_3D,
            factory=decaps,
            schema=DECAPS_SCHEMA,
            size_kind="probabilistic",
            default_mode="mean",
            stamp_distances=(500.0, 2000.0, 4000.0),
            supports_samples=True,
            supports_flags=True,
            api_units="E(B−V)",
            display_units="E(B−V)",
            display_scale=1.0,
            modes=DECAPS_MODES,
            no_coverage_warning="This sightline is outside the DECaPS footprint.",
            infilled_warning=(
                "This sightline was infilled from neighboring pixels; "
                "treat the values with caution."
            ),
        ),
        MapSpec(
            name="edenhofer2023",
            description=(
                "Edenhofer et al. (2023): A 3D dust map based on Gaussian processes "
                "and Gaia-XP-based extinction estimates."
            ),
            citation="Edenhofer et al. (2023)",
            doi="https://doi.org/10.1051/0004-6361/202346165",
            kind=KIND_3D,
            factory=edenhofer2023,
            schema=EDENHOFER_SCHEMA,
            size_kind="probabilistic",
            default_mode="mean",
            stamp_distances=(300.0, 700.0, 1200.0),
            supports_samples=True,
            supports_flags=False,
            requires_distance=True,
            api_units="E (ZGR23)",
            display_units="E(440 nm − 550 nm)",
            display_scale=0.9663921356201177,
            modes=EDENHOFER_MODES,
        ),
        MapSpec(
            name="sfd",
            description="SFD (1998) 2D dust reddening map",
            citation="Schlafly & Finkbeiner (2011)",
            doi="https://doi.org/10.1088/0004-637X/737/2/103",
            kind=KIND_2D,
            factory=sfd,
            schema=SFD_SCHEMA,
            supports_distance=False,
            api_units="E(B−V)",
            display_units="E(B−V)",
        ),
        MapSpec(
            name="csfd",
            description="CSFD 2D dust reddening map (combines SFD, Planck and more)",
            citation="Chiang & Menard (2019)",
            doi="https://doi.org/10.3847/1538-4357/ab1668",
            kind=KIND_2D,
            factory=csfd,
            schema=CSFD_SCHEMA,
            supports_distance=False,
            supports_flags=True,
            api_units="E(B−V)",
            display_units="E(B−V)",
        ),
        MapSpec(
            name="planck-tau353",
            description="Planck 2014 thermal dust optical depth at 353 GHz",
            citation="Planck Collaboration XI (2014)",
            doi="https://doi.org/10.1051/0004-6361/201323195",
            kind=KIND_2D,
            factory=planck("tau353"),
            schema=PLANCK_SCHEMA,
            supports_distance=False,
            api_units="tau_353",
            display_units="tau_353",
        ),
        MapSpec(
            name="planck-radiance",
            description="Planck 2014 thermal dust radiance at 353 GHz",
            citation="Planck Collaboration XI (2014)",
            doi="https://doi.org/10.1051/0004-6361/201323195",
            kind=KIND_2D,
            factory=planck("radiance"),
            schema=PLANCK_SCHEMA,
            supports_distance=False,
            api_units="radiance",
            display_units="radiance",
        ),
        MapSpec(
            name="planck-ebv",
            description="Planck 2014 'recommended' E(B−V) (1.49e4 x tau_353)",
            citation="Planck Collaboration XI (2014)",
            doi="https://doi.org/10.1051/0004-6361/201323195",
            kind=KIND_2D,
            factory=planck("extragalactic"),
            schema=PLANCK_SCHEMA,
            supports_distance=False,
            aliases=("planck",),
            api_units="E(B−V)",
            display_units="E(B−V)",
        ),
        MapSpec(
            name="planck-gnilc",
            description="Planck GNILC 2016 dust opacity map",
            citation="Planck Collaboration (2016)",
            doi="https://doi.org/10.1051/0004-6361/201629057",
            kind=KIND_2D,
            factory=planck_gnilc,
            schema=PLANCK_SCHEMA,
            supports_distance=False,
            api_units="E(B−V)",
            display_units="E(B−V)",
        ),
    ]

    enabled = config.get("ENABLED_MAPS") or []
    if enabled:
        known = {spec.name for spec in specs}
        unknown = [name for name in enabled if name not in known]
        if unknown:
            raise ValueError(f"MAP3D_ENABLED_MAPS contains unknown maps: {unknown}")
        specs = [spec for spec in specs if spec.name in set(enabled)]

    return MapRegistry(specs)
