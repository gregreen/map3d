"""Pages render, and every static asset they reference exists."""

from __future__ import annotations

import re

import pytest

PAGES = ["/", "/cover", "/query", "/usage", "/papers", "/privacy"]

STATIC_REF = re.compile(r'(?:href|src)="(/static/[^"]+)"')


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "<html" in body
    assert "Argonaut" in body


@pytest.mark.parametrize("path", PAGES)
def test_static_references_exist(client, path):
    body = client.get(path).data.decode("utf-8")
    missing = [
        ref
        for ref in set(STATIC_REF.findall(body))
        if client.get(ref).status_code != 200
    ]
    assert not missing, f"{path} references missing assets: {sorted(missing)}"


def test_no_external_asset_requests(client):
    """No CDNs, web fonts or analytics: everything is same-origin."""
    for path in PAGES:
        body = client.get(path).data.decode("utf-8")
        assert "google-analytics" not in body
        assert "googletagmanager" not in body
        assert "fonts.googleapis" not in body
        assert "cdn.jsdelivr" not in body
        assert "maxcdn.bootstrapcdn" not in body
        # Assets are self-hosted; the only allowed external embed is the Vimeo player.
        for asset in re.findall(r'src="(https?://[^"]+)"', body):
            assert asset.startswith("https://player.vimeo.com/"), f"{path}: {asset}"
        for css in re.findall(r'<link[^>]+href="(https?://[^"]+)"', body):
            raise AssertionError(f"{path} loads an external stylesheet: {css}")


def test_query_page_lists_3d_maps_only(client):
    body = client.get("/query").data.decode("utf-8")
    assert 'value="bayestar2019"' in body
    assert 'value="decaps"' in body
    # 2D maps cannot be queried along a line of sight
    assert 'value="sfd"' not in body


def test_query_page_marks_default_map(client):
    body = client.get("/query").data.decode("utf-8")
    assert re.search(r'value="bayestar2019"\s+selected', body)


def test_usage_page_documents_api(client):
    body = client.get("/usage").data.decode("utf-8")
    assert "/api/v2/&lt;map&gt;/query" in body or "/api/v2/<map>/query" in body
    assert "Deprecat" in body
    assert "X-RateLimit-Limit" in body


def test_privacy_page_states_no_ips_stored(client):
    body = client.get("/privacy").data.decode("utf-8")
    assert "IP addresses are personal data" in body
    assert "730" in body


def test_robots_and_sitemap(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /api/" in robots.data.decode()

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.data.decode()


def test_deprecated_legacy_warning_surface(client):
    """The usage page tells users the v1 endpoints still work."""
    body = client.get("/usage").data.decode("utf-8")
    assert "/gal-lb-query-light" in body
