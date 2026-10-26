# Privacy notice for the Argonaut dust-map service

This service answers queries about interstellar dust. To keep it running we count usage,
and to keep it responsive we rate limit it. This page describes exactly what is stored;
the user-facing version is <https://argonaut.skymaps.info/privacy>.

## Summary

* No cookies, no accounts, no advertising or third-party trackers.
* IP addresses are used **in memory** and never written to disk or logs.
* Usage is stored only as daily aggregate counters that cannot identify a person.
* All assets (CSS, JavaScript, fonts, images) are served from this domain.

## What is stored

### `usage_daily` (aggregates only)

| column | meaning |
|---|---|
| `day` | UTC date, e.g. `2026-10-26` |
| `map` | map name, e.g. `bayestar2019` |
| `endpoint` | `api/v2/query`, `interactive/losdata`, … |
| `country` | ISO country code resolved from the client IP, or empty |
| `cell_lat`, `cell_lon` | integer-degree grid cell of the resolved city centroid, or `-1000` |
| `n_queries`, `n_coords` | counters |
| `total_seconds` | summed processing time |

One row per day/map/endpoint/country/cell. There is no row per request, no timestamp finer
than a day, and no identifier linking two requests from the same client.

### `rate_limit` (short-lived counters)

| column | meaning |
|---|---|
| `key` | `HMAC-SHA256(daily_salt, ip_prefix)`, hex |
| `window_start` | start of the fixed window (epoch seconds) |
| `requests`, `work` | counters for that window |

The `ip_prefix` is the IPv4 address, or the /64 network for IPv6 (so rotating within a
subnet does not create new budgets). Rows are deleted once their window has passed; the
salt lives in `rate_limit_salt` for the current day and is deleted afterwards. Without the
salt the hash cannot be linked back to an address, and deleting the salt makes yesterday's
hashes unlinkable.

### Logs

The application writes one line per query to stdout (shipped to CloudWatch on AWS)
containing: request id, endpoint, map name, coordinate count, HTTP status, duration,
country, and cache hit/miss. **No IP address, user agent, referrer or cookie.** Caddy's
access log is configured not to include client IPs; the app relies on its own record.

## Why (legal basis)

Article 6(1)(f) GDPR — legitimate interest in operating, securing and capacity-planning a
scientific service that is free to use. Rate limiting is necessary to keep the service
available for everyone; aggregate statistics are the minimum needed to know which maps
matter and when to scale.

## Retention

| Data | Retention |
|---|---|
| Rate-limit counters | one window (≤ 5 minutes), purged opportunistically |
| Rate-limit salts | current day, older rows deleted |
| `usage_daily` aggregates | 730 days, then deleted (`flask stats-purge`) |
| Application logs | 30 days in CloudWatch (configurable via `log_retention_days`) |

## Data minimization choices

* Geography is resolved in memory per request with the DB-IP Lite City database
  (CC BY 4.0); the IP is discarded when the request ends.
* Only country and a 1° cell are kept, and only inside daily aggregates.
* Geolocation can be disabled entirely with `MAP3D_GEOIP_ENABLED=false`, in which case
  the country and cell columns are blank.
* Google Analytics and all external CDNs were removed in this rewrite.

## Your rights

Because no personal data is retained beyond short-lived pseudonymous counters, access,
rectification and erasure requests normally have nothing to act on. You can still contact
the maintainer (see the site footer) and quote the `X-Request-ID` returned with any
response.

## Controller

The service is operated by the Finkbeiner research group. For questions about this notice,
use the contact address on the site.
