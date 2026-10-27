# TODO — Argonaut rewrite

Progress tracker for the Python 3 / memory-mapped / AWS rewrite. Each entry describes a change,
where it lives, and why it was made. Items follow the numbered goals in the brief; the last two
sections record decisions that differ from the original plan and work that is deliberately deferred.

Legend: `[x]` done · `[~]` partially done · `[ ]` not started

---

## 1. Python 3 migration

- [x] **Port the package to Python 3.** `cStringIO` → `io.BytesIO`, `urllib.quote` →
  `urllib.parse.quote`, `xrange` → `range`, `basestring` → `str`, `print` statements, dict mutation
  during iteration, and implicit sibling imports. Files: `map3d/postage_stamp.py`,
  `map3d/loscurves.py`, `map3d/snippets.py`, `map3d/utils.py`, `map3d/validators.py`,
  `map3d/rasterize.py`, `wsgi.py`, `run.py`.
- [x] **Replace `hputils.py` with `map3d/projections.py`.** The 1,900-line module was imported for
  four symbols. Only the gnomonic projection is kept; `lb2pix`/`pix2lb` now delegate to
  `healpy.ang2pix`/`pix2ang`, and the unused plotting/demo code is gone (still in git history).
- [x] **Delete dead modules.** `redis_logger.py` (replaced by stdlib logging), `gzip_response.py`
  (replaced by Flask-Compress), `forms.py` (unused, and `flask.ext.wtf` no longer exists), the root
  `config.py` (superseded by `map3d/config.py`), `query_argonaut.py` (Python 2 client superseded by
  dustmaps), and `utils/` (superseded by `scripts/`).
- [x] **Modernise the Flask integration.** `app.json_encoder` was removed in Flask ≥ 2.3, so the
  dustmaps encoder now comes from a `DefaultJSONProvider` subclass; requests are decoded explicitly
  with `MultiJSONDecoder` instead of the removed `on_json_loading_failed` hook; `request.json` →
  `get_json`/`get_data`.
- [x] **App factory and blueprints.** `create_app(config)` for testability; views split into
  `views/pages.py`, `views/api_v2.py`, `views/interactive.py`, `views/legacy.py`, plus
  `views/common.py` for shared limit/logging helpers.
- [x] **Pinned dependencies** in `requirements.txt`, project metadata in `pyproject.toml`, and a
  `Makefile` (`install`, `test`, `lint`, `run`, `data`, `images`, `docker-*`).

## 2. dustmaps integration

- [x] **Target dustmaps master.** Installed from `github.com/gregreen/dustmaps` (1.0.14 at the time of
  writing) rather than PyPI; no version pin yet. `ARG DUSTMAPS_REF` in the Dockerfile is the hook for
  pinning later. Local development uses `pip install -e ../dustmaps`.
- [x] **Preserve the `/api/v2` wire format** that `dustmaps.bayestar.BayestarWebQuery()` expects: same
  URL shape, POST body and `MultiJSONEncoder` output (`ndarray_mode='b64'`). Verified against the real
  clients (`BayestarWebQuery`, `SFDWebQuery`) and by a round-trip unit test through dustmaps' own
  decoder.
- [x] **`max_samples` from `MAP3D_MAX_SAMPLES`** (default 5, as before) to bound response size and
  memory; advertised through `/api/v2/maps`.

## 3. Memory-mapped serving and the map registry

- [x] **Declarative registry** (`map3d/maps.py`) replacing the ad-hoc dictionary in `mapdata.py`. One
  entry per map holds the constructor, validation schema, output-size function, stamp distances,
  capability flags, units and citation; it drives the API, the query page, the fetcher and the image
  builder.
- [x] **Maps served.** 3D: `bayestar2015`, `bayestar2017`, `bayestar2019`, `decaps`, `edenhofer2023`.
  2D (API only): `sfd`, `csfd`, `planck-tau353`, `planck-radiance`, `planck-ebv` (the "recommended"
  Planck 2014 E(B−V), alias `planck`), `planck-gnilc`.
- [x] **Lazy construction after the worker forks.** `memmap=True` keeps HDF5/FITS handles open, and
  handles must not be inherited across `fork`, so nothing is opened at import time and gunicorn runs
  without `--preload`. Registration metadata is static, so `/api/v2/maps` never touches a file.
- [x] **Capabilities instead of name checks.** Edenhofer reports no `converged`/reliable-distance
  flags and DECaPS has no `best` mode; the registry records this (`supports_samples`,
  `supports_flags`, `modes`, `requires_distance`) and the views degrade gracefully (no reliability
  band, `mode='mean'` fallback). Edenhofer's own samples were switched on later — see "Edenhofer
  samples" below.
- [x] **Separate API and display units.** Bayestar reports SFD-like arbitrary units, so the registry
  now carries `api_units`, `display_units` and `display_scale`. The JSON API returns raw values; the
  query page plots E(g−r) for Bayestar (0.901 × value, Green et al. 2019 Eq. 30), E(B−V) for DECaPS
  and E(440 nm − 550 nm) for Edenhofer (0.9664 × value, from the extinction curve published with
  that map); the API keeps each map's native units.

## 4. Data pipeline

- [x] **`scripts/fetch_maps.py`** — registry-driven downloads via the dustmaps fetchers, with `--map`,
  `--all`, `--verify`, `--report`, `--force`. Every fetcher defaults to `clobber=False`, so running it
  on a populated directory is a no-op; it only fetches maps added since the volume was seeded. It also
  repacks files that are present but not repacked (the local Bayestar15/17 files are in that state).
- [x] **`scripts/build_stamp_images.py`** — pre-computes nside-512 maps (in each map's page units) at
  the registry's stamp distances, writing `<data>/images/<map>.npy` plus a `.json` sidecar. Files are
  only rebuilt when missing (`--force` overrides), and are saved uncompressed so the app can
  `mmap` them. Measured: ≈45 s per Bayestar/Edenhofer map, ≈2 min for DECaPS.
- [x] **Persistent data layout.** Maps and derived images live under the dustmaps data directory,
  configured with `DUSTMAPS_CONFIG_FNAME` → `{"data_dir": "/data"}` in the container, so the same code
  works with `~/dustmaps_data` locally and the EBS volume on AWS.
- [x] **`scripts/update_geoip.py`** — installs the free DB-IP Lite city database (CC BY 4.0, no
  account), used only to resolve country and a 1° cell in memory.

## 5. Interactive `/query` page

- [x] **Split the 1,315-line jQuery closure into ES modules** (`static/js/query/`): `api.js`,
  `coords.js`, `plot.js`, `stamps.js`, `main.js`.
- [x] **Modern stack** — Bootstrap 5.3 and d3 v7, both vendored under `static/vendor/`; no jQuery, no
  CDN, no web fonts. The modules load natively as `<script type="module">`, so there is no build step
  and no Node toolchain in the image.
- [x] **Same layout and behaviour, plus:** the map selector is built from `/api/v2/maps` (so every 3D
  map with images is available), the distance axis and reliability band follow the map's capabilities,
  coordinate-system switches convert the entered coordinates, in-flight requests are cancelled with
  `AbortController`, the submit button has a busy state, errors are announced with `aria-live`, and
  the page is keyboard-navigable.
- [x] **Postage stamps keep their interaction**: hover reads out ℓ/b on the image, click re-centres the
  query, and the three distance panels come from the pre-built caches.
- [x] **Plot labels** distinguish E(g−r) (Bayestar), E(B−V) (DECaPS) and E(440 nm − 550 nm)
  (Edenhofer), and the legend says "Mean" rather than "Best fit" for maps without samples.

## 6. HTTPS

- [x] **TLS terminated by Caddy** with automatic Let's Encrypt certificates, HTTP→HTTPS redirect and
  HSTS (`docker/Caddyfile`). An ALB + ACM alternative is documented for when HA is needed.
- [x] **Edge security**: strict CSP (all assets same-origin), `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, 10 MB body limit, zstd/gzip, immutable
  caching for `/static/*` and `no-store` for HTML/JSON.
- [x] **No insecure references left in the HTML** (enforced by a test that rejects `http://` assets).

## 7. Containerised AWS deployment

- [x] **`docker/Dockerfile`** — `python:3.12-slim`, pinned requirements, dustmaps from GitHub master,
  non-root user, healthcheck on `/healthz`, `linux/arm64` friendly. Map data is never baked in.
- [x] **`docker/docker-compose.yml`** — `web` (gunicorn 4×2, no `--preload`) plus `caddy`, the data
  volume mounted read-only for serving (writable for maintenance runs), a state volume for SQLite, and
  log rotation.
- [x] **`DEPLOY.md` §9 — capping the compute spend.** The On-Demand vCPU service quota
  (`L-1216C47A`, "Running On-Demand Standard") is lowered to 2 vCPUs, so a second `t4g.large`
  cannot be launched anywhere in the region, by anything. The section also records what the
  quota does *not* cover: `t4g` burst credits (launched with `CpuCredits=standard`),
  EBS/EIP/egress while stopped (~$33/month), and total spend (AWS Budget with an alert).
- [x] **`DEPLOY.md` §10 — cost table**, per month and per year (≈ $84 / ≈ $1,013 on demand,
  ≈ $840 with a one-year compute savings plan, ≈ $2.90 for a day-long test).
- [x] **`DEPLOY.md`** — console-and-compose deployment: launch the instance, add and mount the data
  volume, fetch the maps into it, `compose up`, certificate checks, day-2 operations, sizing,
  scaling path and troubleshooting. Deliberately *not* Terraform/CI-based: a single instance is
  easier to run by hand than to keep an IaC stack and a deploy pipeline in step, and the app is
  reproducible from the image plus a populated volume. (A Terraform + ECR + GitHub Actions variant
  was written and set aside; the files are in the session folder if it is ever wanted.)

## 8. Tests

- [x] **pytest suite with synthetic fixtures** — a tiny repacked Bayestar-format HDF5, a fake 2D map
  and a fake no-samples 3D map, so tests need no downloads.
- [x] **API tests** — every 3D map mode, flags, distances, SkyCoord bodies, unknown map, invalid
  kwargs, `pct` without `percentile`, oversized output, too many coordinates, malformed/empty bodies,
  wrong method, gzip negotiation, rate-limit and security headers.
- [x] **Wire-format compatibility** — responses decoded with `dustmaps.json_serializers` and compared
  to direct map queries; plus live tests using `BayestarWebQuery`/`SFDWebQuery`.
- [x] **Interactive, page and asset tests** — response shape, data-URI images, capability degradation,
  ASCII table, every page renders, every `/static/` reference resolves, no external asset requests.
- [x] **Rate limiting and statistics tests** — request and work budgets, window rollover, endpoint
  isolation, IPv6 /64 bucketing, salted keys, aggregate rows without IPs, retention purge, proxy
  handling of `X-Forwarded-For`.

## 9. Usage limits

- [x] **Two budgets per client**: request count and weighted work units
  (`n_coords × n_samples × n_distance_bins`), so one 10⁵-coordinate call costs as much as many small
  calls. Per-request caps remain (`MAP3D_MAX_OUTPUT_VALUES`, `MAP3D_MAX_COORDS`,
  `MAX_CONTENT_LENGTH`).
- [x] **Salted, short-lived keys**: `HMAC-SHA256(daily salt, IPv4 address or IPv6 /64)`; the salt is
  shared by all workers through SQLite and discarded after the day. Plain IPs are never persisted.
- [x] **Global concurrency guard** per worker (503 + `Retry-After` instead of queueing until the proxy
  times out).
- [x] **Standard headers and helpful errors**: `X-RateLimit-Limit/Remaining/Reset`, `Retry-After`, and
  a 429 body that suggests batching coordinates.
- [ ] **Later, if abuse persists:** proxy-level `limit_req` (nginx) or the `caddy-ratelimit` plugin as a
  cheap first line; optional API keys with higher budgets for large pipelines.

## 10. Database: Redis → SQLite

- [x] **Recommendation implemented: SQLite instead of Redis.** One node, a handful of counters and one
  upsert per query. SQLite in WAL mode needs no extra service, survives restarts, is backed up as a
  single file, and has ample headroom here. Redis becomes the right answer only when running several
  instances behind a load balancer.
- [x] **`map3d/db.py`** — schema creation, WAL, `busy_timeout`, `synchronous=NORMAL`, and short
  `BEGIN IMMEDIATE` transactions; counters use `INSERT … ON CONFLICT DO UPDATE` so concurrent workers
  cannot lose increments.
- [x] **Expired rate-limit rows are purged opportunistically** (every 500 checks) and by
  `flask rate-limit-purge`; usage aggregates are purged by `flask stats-purge`.

## 11. Logging

- [x] **Stdlib `logging`** (`map3d/logging_setup.py`) with one stdout handler for Docker/CloudWatch,
  configurable level, and `event key=value` records.
- [x] **Structured query records**: request id, endpoint, map, coordinate count, status, duration,
  country, cache behaviour — no IP addresses, user agents or referrers.
- [x] **No duplicate access log**: gunicorn's access log is off; the app's record carries the timing.

## 12. Anonymous, GDPR-compliant usage statistics

- [x] **Only aggregates are stored**: `usage_daily(day, map, endpoint, country, cell_lat, cell_lon,
  n_queries, n_coords, total_seconds)`. No IPs, no user agent, no cookie, no per-request row, no
  timestamp finer than a day, and exact counts (no suppression).
- [x] **Geography resolved in memory** with DB-IP Lite City and an LRU cache, then discarded. Can be
  switched off with `MAP3D_GEOIP_ENABLED=false`.
- [x] **Documented** in `PRIVACY.md` and on the `/privacy` page: what is stored, the legal basis
  (legitimate interest), retention (730 days for aggregates, one window for counters) and how to
  export or purge.
- [x] **Google Analytics and all external asset hosts removed.**

## 13. Additional upgrades

- [x] **`/api/v2/maps`** — machine-readable map list (type, units, modes, distance range, DOI). It
  powers the query page's selector and documents new maps automatically.
- [x] **`/api/v2/openapi.json`**, **`/healthz`**, **`/readyz`** (DB, data directory, map count).
- [x] **`/api/v2/stats`** — public, geography-free totals per map.
- [x] **JSON errors with request ids**, no tracebacks in responses, `413`/`429`/`503` where
  appropriate.
- [x] **`ProxyFix` with a configurable hop count** so client IPs are right behind Caddy without
  trusting forged headers (tested both ways).
- [x] **`robots.txt`** disallowing `/api/`, a **sitemap**, and a privacy page linked from the footer.
- [x] **Docs**: rewritten `README.md`, new `DEPLOY.md` and `PRIVACY.md`, and a usage page with current
  Python 3 / dustmaps / HTTP examples (the data-cube example figure was regenerated from the real
  Bayestar19 file, and its upsampling code was corrected while doing so).

## Decisions that differ from the first plan

- **No esbuild/Node in the image.** The query page's modules are plain ES modules served directly, and
  Bootstrap/d3 are vendored. This removes a whole toolchain from the build while keeping the same
  code structure; the cost is a handful of extra HTTP requests (kept cheap by long-lived caching).
- **Stamp caches are `.npy` + `.json`, not `.npz`.** `numpy` cannot memory-map members of an `.npz`
  archive, and memory-mapping is the point.
- **Edenhofer 2023 uses the repacked HDF5 file** (picked up automatically by dustmaps when present) so
  the read-only data volume is never modified by an in-place FITS transform.
- **The page plots E(g−r) for Bayestar, as the original site did**, rather than relabelling to E(B−V).
  Units are now explicit per map in the registry and documented on the usage page.
- **`utils/` and `query_argonaut.py` deleted** rather than ported; both are superseded by `scripts/`
  and by dustmaps itself.

## Follow-ups deliberately deferred

- [ ] Pin dustmaps to a commit SHA, or to the next PyPI release once it lands (`ARG DUSTMAPS_REF`).
- [x] **Edenhofer 2023 samples are served** (≈20 GB of extra data); see "Edenhofer samples" below.
- [ ] 2D maps (SFD, CSFD, Planck) on the interactive page — currently API-only, per the brief.
- [ ] Optional API keys with higher rate limits for large survey pipelines.
- [ ] ALB + Auto Scaling Group if traffic outgrows one instance (requires moving rate limiting and
  statistics off SQLite).
- [x] **Repack the local Bayestar15/17 files** — done; `repacked` is now set and the files match
  `dustmaps.bayestar.REPACKED_SIZES` (4.61 GB and 5.08 GB).
- [x] **Stamp images for Bayestar15/17** — built (nside 512, 300 pc / 1 kpc / 5 kpc, ≈100 s each).
  Every interactive map now has its three panels.
- [ ] Consider a higher `MAP3D_STAMP_NSIDE` (1024) on the deployment for finer stamps (≈4× build time).
- [x] **Repacking was never broken — it was two repacks writing the same file.** An earlier note
  here blamed `h5py` 3.16.0 / HDF5 2.0.0 for a `ValueError: ... (bad object header version number)`
  in `h5_repack`, and suggested pinning `h5py`. That was wrong: `dustmaps.bayestar.fetch()` writes
  the repacked map to `<map>.h5.repacked`, so a second repack started by hand while the first was
  running targets the *same* path, and one process then reads object headers the other is rewriting.
  Re-running `h5_repack` alone in the same venv (HDF5 2.0.0) succeeds, 126 s for bayestar2019, and
  the output is byte-for-byte the size of the file we serve, with identical `samples` values and
  `repacked`/`chunk_pixels` attributes. No dependency pin is needed, and nothing about the
  deployment changes. The lesson for `fetch_maps.py` users: it is idempotent, but do not run two
  copies against one data directory at the same time.

## Review fixes

- [x] **`Privacy` moved from the top bar to the footer** (`layout.html`). The top nav is now
  Overview / Query map / Access & docs / Papers.
- [x] **Licensing copy corrected.** "3D dust maps from the Finkbeiner research group" and the blanket
  "Data are released under CC BY-SA 4.0" claim are gone: the maps are not all from one group and
  each is released under the terms its own team chose. Both the footer and the usage page's License
  section now only state that the code snippets are MIT licensed; map citations and data releases
  are left to the papers page.
- [x] **The no-data banner now says which problem it is.** One sentence was being used for three
  different situations. The registry holds three wordings per map — `warning` (a fit that did not
  converge inside the footprint), `no_coverage_warning` (a sightline with no data at all, i.e.
  outside the survey footprint) and `infilled_warning` (DECaPS pixels filled from their neighbors) —
  and `views/interactive.py::_warning_for` picks one from the map's flags plus whether any value came
  back:
  | situation | Bayestar | DECaPS |
  |---|---|---|
  | all values NaN | "This sightline is outside the Bayestar footprint." | "…outside the DECaPS footprint." |
  | finite, fit failed | "The line-of-sight fit did not converge…" | same, unless the pixel was infilled |
  | finite, infilled | — | "This sightline was infilled from neighboring pixels…" |

  Verified on the real maps: Bayestar at (0°, −45°) now reports the footprint message instead of a
  convergence failure, while (180.3°, +53.8°) — covered, but with a fit that failed — keeps the
  convergence caution. `/losdata` sends `warning` and `infilled`; the page shows the banner whenever a
  warning is present rather than keying off `converged` alone.
- [x] **Unreliable distances are hatched and labelled, as on the original site.** The plot no longer
  tints a "reliable range" band (which left the reader to work out what the tint meant); instead the
  distances *outside* the map's reliable span are covered by the old site's faint diagonal hatch, with
  a rotated caption reading "unreliable" knocked out of it, in both directions. The SVG defines the
  pattern as a `<pattern>` (8 px cell, 3 px stroke, 6 % opacity) and the caption uses a white
  `paint-order: stroke` halo rather than the old mask pair, which looks the same and is a fraction of
  the code. Cases handled, all driven by `min_reliable_distmod` / `max_reliable_distmod`: an ordinary
  span gives two panels; a span that reaches the edge of the plot gives one; a sightline the map
  reports no reliable range for (the 999/-999 sentinels) hatches the whole plot with a single caption,
  as the old site did; and a map that reports no flags at all (Edenhofer) gets no hatching. Captions
  are omitted when a panel is too narrow to hold one. The captions sit at 60 % opacity so they read as
  background, and they slide with their panels when a new query moves the boundaries (a caption that
  was hidden appears in place rather than flying in from its previous position). A sightline the map
  has no data for is a different case, and says so: the whole plot is hatched and the caption reads
  **"outside map footprint"**, horizontally, in the same style. `/losdata` grew an `in_footprint`
  flag for that (the same test the warning wording uses), so the plot does not have to infer it.
- [x] **Red hover dot removed from the postage stamps.** The browser's `crosshair` cursor is the
  pointer, so the JS-drawn dot could only ever trail behind it. The centred crosshairs (which mark
  the query direction) and the hover coordinate readout are unchanged, and clicking a panel still
  re-centres the query.
- [x] **Edenhofer 2023 is displayed as E(440 nm − 550 nm).** The map reports E in the ZGR23 band,
  which the API still returns unchanged; the query page now multiplies by 0.9663921356201177, the
  conversion taken from the extinction curve published with the map
  (<https://zenodo.org/records/7811871>), and labels the plot, readout and stamp panels accordingly.
  This is a registry change (`display_units`, `display_scale`), plus a rebuild of the
  `edenhofer2023` stamp cache, which stores display-scaled values.
- [x] **Bayestar 2015/2017 repacked and their stamp caches built**, so every interactive map now has
  its three panels (see the data items above).
- [x] **Map descriptions on the query page replaced with the maintainer's wording** (Pan-STARRS 1 /
  2MASS / WISE / Gaia DR2 for Bayestar, DECaPS2 / 2MASS / VVV / unWISE / Gaia DR3 for DECaPS, Gaussian
  processes for Edenhofer), kept verbatim in the registry so `/api/v2/maps` and the page agree. The
  metadata that follows (units, reliable distance, samples) is now joined with a middle dot rather
  than an em dash, since the descriptions end in a full stop.
- [x] **Coordinate-system switch no longer throws.** Loading a `coordsys=equ` URL and then clicking
  "Galactic" called the converter with `from === to`, because the previous system was tracked in a
  local variable that `setInputs` (which sets the radio programmatically) never updated; the
  conversion threw `TypeError: … reading 'toFixed'` and left the inputs unconverted. The current
  system now lives in `state.coordsys` and the converter is a no-op when the two agree.
- [x] **Navigation and API naming.** The top-nav item "Access & docs" is now "Documentation", the
  "HTTP API" section and table-of-contents entry are now "Query API", and that section opens by
  recommending the `dustmaps` Python package over calling the endpoint directly. The "Query map"
  label is now "Interactive query" (nav, overview tile and the `/cover` page).
- [x] **Overview page polish.** The three top links are icon tiles on the banner (translucent,
  rounded, hover lift) instead of white boxes with a heading, and the section headings now clearly
  outrank the video captions (30 px vs 18 px; the browser's default scale had them inverted at
  21 px vs 33 px). The "interactive query page" link in the intro paragraph pointed at `/usage` and
  now goes to `/query`.
- [x] **Snippet-licence note kept only where the snippets are.** The MIT line is gone from the shared
  footer (which now carries just the API / map list / cite / privacy links) and remains in the
  Documentation page's License section.
- [x] **`/query` retitled "Interactively query the dust maps"** (page heading and browser title), with
  the one-line subtitle under it dropped. The Documentation page keeps its own title, "Accessing the
  maps", and its subtitle (which now names the Query API).
- [x] **American spellings on every page.** `centre/centred/re-centre`, `labelled`, `serialised`
  and `towards` replaced on the query, usage and expo pages; the rendered text of `/`, `/query`,
  `/usage`, `/papers`, `/privacy` and `/expo` now scans clean for a list of British spellings, as
  does the ASCII line-of-sight table.
- [x] **Edenhofer 2023 posterior samples served.** The map now comes from
  `dustmaps.edenhofer2023.Edenhofer2023Query(load_samples=True, integrated=True, memmap=True)`
  (the FITS map, memory-mapped, 20 GB on disk, ~370 MB RSS in the server), replacing the
  mean/std-only HDF5 reader. The API gains `std`, `samples` and `random_sample` modes; the
  interactive page draws Edenhofer's 12 samples as the faint curves and gets a 16–84th percentile
  band for the first time. Because that map needs a distance for every query, its curve is sampled
  at 64 distances along the line of sight (`CURVE_POINTS`) rather than from a stored grid, and the
  posterior is transposed into the `(n_samples, n_distances)` shape the plot expects. Supporting
  changes: `distance_moduli()` reads the radial bins from the FITS record, `output_size()` counts
  its samples and radii, `scripts/fetch_maps.py` fetches with `fetch_samples=True`, the curve is
  labelled "Mean" where a map has no `best` mode (it was keyed off samples being present), and the
  ASCII line-of-sight table now takes its units and first-row label from the map instead of always
  claiming `E(g−r)` and "best fit".
- [x] **The line-of-sight plot interpolates between distance bins and animates on update.** The
  pointer position is no longer snapped to the nearest distance bin: the readout, the hover dot and
  the 16th/84th-percentile band are read from a linear interpolation between the two neighbouring
  bins, so the dot rides exactly on the drawn median curve and the numbers change continuously as
  the pointer moves. Successive queries for the same map now reuse the existing SVG (state kept per
  element) and d3 transitions paths, axes, the reliable-distance shading and the y-scale over 500 ms,
  which is what makes a change of sky position glide instead of snapping; a change of map rebuilds,
  since the distance grid differs.
- [x] **Unit labels use a true minus sign (U+2212)** wherever a hyphen stood for subtraction:
  `E(g−r)`, `E(B−V)`, `E(440 nm − 550 nm)`, and `(3.518 − 2.617)` in the usage page. The change
  starts in the registry (`api_units` / `display_units`), so the API, the query page and the usage
  table agree, and it propagates to the code snippets, the `lostable` header and the docs. The
  `lostable` endpoint is now served as `text/plain; charset=utf-8` (it was US-ASCII). Numeric values
  keep ASCII minus signs — input fields, tick labels and table cells stay copy-pasteable and parseable.
- [x] **Every map declares the complete set of query arguments it accepts.** `MapSpec.schema` is now
  a required field (an empty dict where a map has none), so a map cannot be added without deciding
  what the API may forward to it, and `MapSpec.__post_init__` cross-checks the schema against the
  rest of the spec: it may only contain `mode`, `pct`, `return_flags` and `order`; `pct` requires
  `mode`; `return_flags` must agree with `supports_flags`; the values allowed for `mode` must equal
  the declared `modes` and its default must equal `default_mode`; and `order` is rejected on a 3D
  map. Two schemas were added: `CSFD_SCHEMA` (`return_flags`, which returns CSFD's large-scale
  structure / no-IRAS / cosmology bit mask — CSFD rejected it before) and `PLANCK_SCHEMA` (empty:
  the Planck 2014 components and GNILC take no query arguments, the component being fixed by which
  map was requested). Shared field definitions are now builders (`_mode_field`, `_pct_field`,
  `_return_flags_field`) instead of one dict aliased between maps, so tuning one map's percentiles
  can no longer change another's. `/api/v2/maps` publishes `query_kwargs` per map, `output_size()`
  counts the flags array so `return_flags` cannot slip past `MAX_OUTPUT_VALUES`, and the
  Documentation page now lists the per-map arguments (and explains what CSFD's bits mean).
- [x] **`seed_or_rng` exposed on the maps that support it, integers only.** Bayestar 2015/2017/2019,
  DECaPS and Edenhofer 2023 accept a random seed, so `mode: "random_sample"` and
  `"random_sample_per_pix"` can now be made reproducible (the same seed returns the same draw; a
  different seed returns a different one). The schema takes an integer only: `dustmaps` also accepts
  a `numpy.random.Generator` so a caller can continue its own stream, but that has no JSON
  representation we are willing to serialize — or to accept from a client — so the API rejects it
  (there is nothing to serialize and no deserializer to trust). Validation is cerberus's `integer`
  type with `min: 0` plus a `check_with` rule that rejects booleans, which Python would otherwise
  accept as integers (`seed_or_rng: true` would silently become seed 1). `null` or an absent key
  keeps OS-seeded randomness. A registry invariant requires `supports_samples` for any map that
  declares the argument. The OpenAPI document and the Documentation page list the new argument.
- [x] **Query-size estimation is now per map, and its arithmetic is verified.** `MapSpec` carries a
  required `size_estimator`, so each map states how many values its queries return instead of one
  function guessing from the shape of the query object: `size_flat_map` (SFD, the Planck 2014 maps,
  GNILC — one value per coordinate), `size_flat_map_with_flags` (CSFD — a value and a flag record
  per coordinate), `size_probabilistic` (Bayestar and DECaPS — the map's own `get_query_size`, plus
  one flag record per coordinate when flags are asked for) and `size_edenhofer` (one value per
  coordinate, or per stored sample). The old `size_kind` field is gone, since the estimator
  supersedes it, and a registry invariant requires a flags-aware estimator for any map that supports
  flags. The previous blanket "×2 when `return_flags` is set" was wrong wherever samples or distance
  bins were involved, because flags hold one record per coordinate: Bayestar `mode=samples` without
  a distance was overcharged about twofold (2400 predicted against 1202 actual) and with a distance
  by two thirds (20 against 12). Measured against all eleven real maps — every mode, with and
  without a distance, with and without flags, scalar and 2-D coordinate arrays, scalar and array
  `d`, scalar and array `pct` — the prediction now equals the value count exactly (231/231
  combinations at ratio 1.00), and a parametrized test holds every map to ±20%.
- [x] **Work-unit budget is visible to clients, and a work rejection says so.** Only the request-count
  budget had headers, so a client that exhausted `RATE_LIMIT_API_WORK` was rejected with
  `X-RateLimit-Remaining: 92` and a body reporting `"limit": 100` — the request limit it had never
  come near — with nothing mentioning work units at all. `LimitResult` now carries `work_limit` and
  `work_remaining`, responses gain `X-RateLimit-Work-Limit` and `X-RateLimit-Work-Remaining`, and the
  429 body gains `exceeded` (`"requests"` or `"work"`), `remaining`, `work_limit`, `work_remaining`
  and `requested_work` (the cost of the rejected request), so a client can see that its query was
  too big rather than too frequent and can shrink it to fit. `X-RateLimit-Reset` keeps its
  epoch-seconds meaning; `Retry-After` remains the seconds-remaining field to follow.
