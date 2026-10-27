"""Rate limiting, usage statistics and GeoIP behaviour."""

from __future__ import annotations

import calendar
import time

import pytest

from map3d.db import Database
from map3d.geoip import GeoLocation
from map3d.rate_limit import RateLimiter, ip_prefix, salted_key
from map3d.usage_stats import UsageStats


def _query(client):
    return client.post("/api/v2/sfd/query", json={"l": 10.0, "b": 10.0})


def test_request_count_limit(client, app):
    app.config["RATE_LIMIT_API_REQUESTS"] = 2
    assert _query(client).status_code == 200
    assert _query(client).status_code == 200
    r = _query(client)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert int(r.headers["X-RateLimit-Remaining"]) == 0
    assert "batch" in r.get_json()["error"] or "multiple" in r.get_json()["error"]
    payload = r.get_json()
    assert payload["exceeded"] == "requests"
    assert payload["remaining"] == 0
    assert payload["work_remaining"] > 0


def test_work_budget_limits_large_requests(client, app):
    app.config["RATE_LIMIT_API_REQUESTS"] = 1000
    app.config["RATE_LIMIT_API_WORK"] = 10  # smaller than one samples-mode query
    r = client.post(
        "/api/v2/bayestar2019/query",
        json={"l": 10.0, "b": 10.0, "mode": "samples"},
    )
    assert r.status_code == 429
    # The rejection is about work units, and says so, even though the request
    # count is untouched.
    payload = r.get_json()
    assert payload["exceeded"] == "work"
    assert payload["requested_work"] > payload["work_limit"]
    assert payload["work_remaining"] == payload["work_limit"]
    assert payload["remaining"] > 0
    assert int(r.headers["X-RateLimit-Remaining"]) > 0
    assert int(r.headers["X-RateLimit-Work-Remaining"]) == 10


def test_work_headers_track_a_query_cost(client, app):
    app.config["RATE_LIMIT_API_REQUESTS"] = 1000
    app.config["RATE_LIMIT_API_WORK"] = 1_000_000
    first = _query(client)
    assert first.status_code == 200
    limit = int(first.headers["X-RateLimit-Work-Limit"])
    spent = limit - int(first.headers["X-RateLimit-Work-Remaining"])
    assert spent == 1  # one coordinate, one value

    # A samples-mode query over the same coordinate costs one unit per sample
    # and per distance bin, which the headers now show.
    heavy = client.post(
        "/api/v2/bayestar2019/query", json={"l": 10.0, "b": 10.0, "mode": "samples"}
    )
    assert heavy.status_code == 200
    remaining = int(heavy.headers["X-RateLimit-Work-Remaining"])
    assert limit - remaining - spent > 1


def test_limits_are_per_endpoint_kind(client, app):
    app.config["RATE_LIMIT_INTERACTIVE_REQUESTS"] = 1
    url = "/api/v2/interactive/bayestar2019/losdata?lon=120&lat=10&coordsys=gal"
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429
    # A separate budget applies to the query API
    assert _query(client).status_code == 200


def test_ip_prefix_normalisation():
    assert ip_prefix("192.168.1.5") == "192.168.1.5"
    assert ip_prefix("2001:db8:1:2:3:4:5:6") == "2001:db8:1:2::/64"
    # Rotating within a /64 must not create a new bucket
    assert ip_prefix("2001:db8:1:2::1") == ip_prefix("2001:db8:1:2:ffff::9")
    assert ip_prefix("::ffff:10.0.0.1") == "10.0.0.1"


def test_salted_key_is_stable_and_salt_dependent():
    a = salted_key("1.2.3.4", "pepper")
    assert a == salted_key("1.2.3.4", "pepper")
    assert a != salted_key("1.2.3.4", "other")
    assert "1.2.3.4" not in a


def test_limiter_window_rollover(tmp_path):
    db = Database(tmp_path / "rl.sqlite3")
    db.initialize()
    limiter = RateLimiter(db)
    key = limiter.client_key("1.2.3.4", now=1000.0)

    first = limiter.check(
        key, requests_limit=1, work_limit=100, work=0, window=60, now=1000.0
    )
    second = limiter.check(
        key, requests_limit=1, work_limit=100, work=0, window=60, now=1010.0
    )
    later = limiter.check(
        key, requests_limit=1, work_limit=100, work=0, window=60, now=1070.0
    )

    assert first.allowed and first.remaining == 0
    assert not second.allowed
    assert later.allowed


def test_limiter_purges_expired_rows(tmp_path):
    db = Database(tmp_path / "rl.sqlite3")
    db.initialize()
    limiter = RateLimiter(db)
    key = limiter.client_key("5.6.7.8", now=0.0)
    limiter.check(key, requests_limit=5, work_limit=5, window=60, now=0.0)
    assert limiter.purge(before=3600) == 1


class FakeGeoIP:
    def __init__(self, location):
        self.location = location

    def lookup(self, ip):
        return self.location


def _stats(tmp_path, location=GeoLocation("FR", 48.85, 2.35)):
    db = Database(tmp_path / "usage.sqlite3")
    db.initialize()
    return UsageStats(db, FakeGeoIP(location)), db


def test_usage_records_only_aggregates(tmp_path):
    stats, db = _stats(tmp_path)
    for _ in range(3):
        stats.record(
            map_name="bayestar2019",
            endpoint="api/v2/query",
            ip="9.9.9.9",
            n_coords=10,
            seconds=0.5,
            now=calendar.timegm(time.strptime("2026-01-02", "%Y-%m-%d")),
        )

    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM usage_daily").fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(usage_daily)")]

    assert "ip" not in columns
    assert len(rows) == 1
    row = rows[0]
    assert row["day"] == "2026-01-02"
    assert row["country"] == "FR"
    assert (row["cell_lat"], row["cell_lon"]) == (48, 2)
    assert row["n_queries"] == 3
    assert row["n_coords"] == 30
    assert row["total_seconds"] == pytest.approx(1.5)


def test_usage_unknown_location(tmp_path):
    stats, db = _stats(tmp_path, location=GeoLocation(""))
    stats.record(map_name="sfd", endpoint="api/v2/query", ip="1.1.1.1", now=0.0)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM usage_daily").fetchone()
    assert row["country"] == ""
    assert row["cell_lat"] == -1000


def test_usage_totals_and_export(tmp_path):
    stats, _ = _stats(tmp_path)
    now = time.time()
    stats.record(map_name="sfd", endpoint="e", ip=None, n_coords=5, seconds=0.1, now=now)
    stats.record(map_name="sfd", endpoint="e", ip=None, n_coords=5, seconds=0.1, now=now)

    totals = stats.totals(days=1, now=now)
    assert totals[0]["map"] == "sfd"
    assert totals[0]["n_queries"] == 2

    csv_text = stats.export_csv(days=1, now=now)
    assert csv_text.splitlines()[0].startswith("day,map,endpoint,country")
    assert "sfd" in csv_text


def test_usage_purge(tmp_path):
    stats, _ = _stats(tmp_path)
    old = calendar.timegm(time.strptime("2000-01-01", "%Y-%m-%d"))
    stats.record(map_name="sfd", endpoint="e", ip=None, now=old)
    assert stats.purge() == 1


def test_usage_disabled(tmp_path):
    db = Database(tmp_path / "usage.sqlite3")
    db.initialize()
    stats = UsageStats(db, FakeGeoIP(GeoLocation("")), enabled=False)
    stats.record(map_name="sfd", endpoint="e", ip="1.1.1.1")
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM usage_daily").fetchone()[0] == 0


def test_uses_forwarded_client_ip_behind_proxy(app_factory):
    """With ProxyFix enabled, the forwarded address is what gets bucketed/logged."""
    app = app_factory(TRUSTED_PROXY_HOPS=1)
    svc = app.extensions["map3d"]
    seen = []

    from map3d.geoip import GeoLocation

    svc.geoip.lookup = lambda ip: (seen.append(ip), GeoLocation("DE", 52.5, 13.4))[1]

    client = app.test_client()
    response = client.post(
        "/api/v2/sfd/query",
        json={"l": 10.0, "b": 10.0},
        headers={"X-Forwarded-For": "8.8.4.4"},
    )
    assert response.status_code == 200
    assert seen == ["8.8.4.4"]

    with svc.db.connect() as conn:
        row = conn.execute(
            "SELECT country, cell_lat, cell_lon FROM usage_daily"
        ).fetchone()
    assert row["country"] == "DE"
    assert (row["cell_lat"], row["cell_lon"]) == (52, 13)


def test_without_proxy_fix_forwarded_header_is_ignored(app_factory):
    app = app_factory(TRUSTED_PROXY_HOPS=0)
    svc = app.extensions["map3d"]
    seen = []
    svc.geoip.lookup = lambda ip: (seen.append(ip), GeoLocation("US"))[1]

    client = app.test_client()
    client.post(
        "/api/v2/sfd/query",
        json={"l": 10.0, "b": 10.0},
        headers={"X-Forwarded-For": "8.8.4.4"},
    )
    assert seen and seen[0] != "8.8.4.4"
