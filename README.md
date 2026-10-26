# Argonaut — 3D interstellar dust maps

Web service for the 3D interstellar dust maps produced by the Finkbeiner research group
(Pan-STARRS 1 + 2MASS + Gaia). It serves <https://argonaut.skymaps.info>:

* an interactive **query page** for single lines of sight,
* a **JSON API** used by `dustmaps` (`dustmaps.bayestar.BayestarWebQuery`),
* download and citation documentation.

Supported maps: Bayestar 2015/2017/2019, DECaPS, Edenhofer 2023 (3D, with posterior
samples), plus SFD, CSFD, Planck 2014 (τ₃₅₃, radiance, recommended E(B−V)) and Planck GNILC
(2D, API only).

## Design at a glance

| Concern | Choice | Why |
|---|---|---|
| Web framework | Flask 3 + gunicorn | The app is a thin validation layer over `dustmaps`; keeping Flask avoids touching the wire format that `BayestarWebQuery` depends on. |
| Map access | `memmap=True` in dustmaps | Queries read only the HDF5 chunks they need, so a small instance can serve many large maps. Query objects are built lazily **after** the worker forks. |
| Database | SQLite (WAL) | A handful of counters and daily aggregates on one node. No extra service, survives restarts, one file to back up. |
| Rate limiting | SQLite, two budgets | Request count *and* work units (coordinates × samples × distance bins). Keys are salted HMACs of the IP prefix; plain IPs are never stored. |
| Statistics | Aggregated in SQLite | Day × map × endpoint × country × 1° cell, exact counts, no per-request rows. See [PRIVACY.md](PRIVACY.md). |
| Frontend | Bootstrap 5 + d3 v7 + native ES modules | No jQuery, no CDN, no build step: the browser loads `static/js/query/*.js` directly. |
| TLS | Caddy | Automatic Let's Encrypt certificates, HSTS, strict CSP. |
| Deployment | EC2 + Docker Compose + EBS | Memory-mapped maps need local disk (not Fargate/EFS). See [DEPLOY.md](DEPLOY.md). |

## Quick start (local)

The map files are large and are **not** in this repository. If you already have a dustmaps
data directory (e.g. `~/dustmaps_data`), point the app at it; otherwise download what is
missing.

```bash
make install                # .venv + requirements + dustmaps (local ../dustmaps or GitHub)
export MAP3D_DATA_DIR=$HOME/dustmaps_data
make data                   # download any missing maps (no-op if already present)
make images                 # build postage-stamp caches (optional for the API)
make run                    # http://127.0.0.1:5000
```

`make test` runs the suite (synthetic fixtures — no downloads needed).

With Docker:

```bash
cp .env.example .env        # set SITE_ADDRESS=localhost for a local run
make docker-up              # web + Caddy on http://localhost
```

## Configuration

Everything is read from the environment; see [map3d/config.py](map3d/config.py).

| Variable | Default | Purpose |
|---|---|---|
| `MAP3D_DATA_DIR` | dustmaps `data_dir()` | Map files (read-only in production). |
| `MAP3D_IMAGES_DIR` | `$MAP3D_DATA_DIR/images` | Pre-built stamp images. |
| `MAP3D_STATE_DIR` | `./var` | SQLite database and scratch state. |
| `MAP3D_SQLITE_PATH` | `$STATE_DIR/map3d.sqlite3` | Override the database location. |
| `MAP3D_MAX_SAMPLES` | `5` | Samples per query; bounds output size and memory. |
| `MAP3D_STAMP_NSIDE` | `512` | Resolution of stamp images (1024 gives finer detail, 4× slower to build). |
| `MAP3D_IMAGE_CACHE_SIZE` | `4` | Number of stamp caches kept mapped at once. |
| `MAP3D_MAX_OUTPUT_VALUES` | `1000000` | Largest allowed response (values). |
| `MAP3D_MAX_COORDS` | `500000` | Largest allowed number of coordinates. |
| `MAP3D_RATE_LIMIT_*` | see config | Per-window request and work-unit budgets. |
| `MAP3D_GEOIP_DB` | `$STATE_DIR/dbip-city-lite.mmdb` | DB-IP Lite / GeoLite2 city database (optional). |
| `MAP3D_GEOIP_ENABLED` | `true` | Set `false` to skip geography entirely. |
| `MAP3D_USAGE_RETENTION_DAYS` | `730` | Aggregate retention. |
| `MAP3D_TRUSTED_PROXY_HOPS` | `1` | `ProxyFix` trust; set `0` when running without a proxy. |
| `DUSTMAPS_CONFIG_FNAME` | — | Points dustmaps at a config file with `data_dir`. |

## API

`POST /api/v2/<map>/query` — JSON in, JSON out, with the exact encoding produced by
`dustmaps.json_serializers` (base64 arrays, tagged `SkyCoord`/`Quantity`).

```bash
curl -s https://argonaut.skymaps.info/api/v2/bayestar2019/query \
     -H 'Content-Type: application/json' \
     -d '{"l": 150.0, "b": 20.0, "d": 1.0, "mode": "best"}'
```

* `GET /api/v2/maps` — maps, units, supported modes, distance ranges.
* `GET /api/v2/openapi.json` — OpenAPI description.
* `GET /api/v2/stats` — anonymous aggregate query counts.
* `GET /api/v2/interactive/<map>/losdata` — curve + postage stamps for the query page.
* `GET /healthz`, `GET /readyz` — liveness and readiness.

Errors are JSON with a `request_id`; oversized requests return `413`, excess traffic `429`
with `Retry-After` and `X-RateLimit-*` headers. `POST /gal-lb-query-light` and
`GET /gal-lb-query` still work but are deprecated.

## Data pipeline

```bash
python scripts/fetch_maps.py --all        # idempotent: only fetches what is missing
python scripts/fetch_maps.py --verify     # constructs every map; flags unrepacked HDF5 files
python scripts/fetch_maps.py --report     # on-disk sizes per map
python scripts/build_stamp_images.py --all
python scripts/update_geoip.py            # optional: country attribution for statistics
```

`fetch_maps.py` uses the dustmaps fetchers, which repack files for memory-mapped access.
An existing but unrepacked Bayestar file is repacked in place rather than re-downloaded.

## Layout

```
map3d/
  __init__.py        app factory, JSON provider, error handlers
  maps.py            declarative map registry (single source of truth)
  views/             pages, api_v2, interactive, legacy
  rate_limit.py      SQLite-backed limits (requests + work units)
  usage_stats.py     aggregate, non-identifying statistics
  geoip.py           offline country/city lookup
  postage_stamp.py   stamp rasterizing and encoding
  projections.py     gnomonic projection + HEALPix helpers
  static/js/query/   ES modules for the query page
scripts/             fetch_maps.py, build_stamp_images.py, update_geoip.py
docker/              Dockerfile, compose, Caddyfile, dustmapsrc
tests/               pytest suite with synthetic map fixtures
```

## Documentation

* [DEPLOY.md](DEPLOY.md) — first deployment, seeding data, operations, costs.
* [PRIVACY.md](PRIVACY.md) — exactly what is logged and for how long.
* [TODO.md](TODO.md) — the migration checklist, including follow-ups.
