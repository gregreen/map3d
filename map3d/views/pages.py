"""Static and semi-static pages, plus health checks."""

from __future__ import annotations

import logging
import os

from flask import Blueprint, Response, current_app, jsonify, render_template

from .. import __version__, services
from .. import snippets as snippets_module

log = logging.getLogger(__name__)

bp = Blueprint("pages", __name__)


@bp.get("/")
def expo():
    return render_template("expo.html")


@bp.get("/cover")
def cover():
    return render_template("cover.html")


@bp.get("/papers")
def papers():
    return render_template("papers.html")


@bp.get("/query")
def query():
    svc = services()
    # Every 3D map is selectable: the interactive endpoint degrades to "no
    # postage stamps" when an image cache has not been built yet.
    maps_3d = svc.registry.public_metadata(include_2d=False)
    default_map = "bayestar2019" if "bayestar2019" in maps_3d else next(iter(maps_3d), None)
    return render_template(
        "query.html",
        maps=maps_3d,
        default_map=default_map,
        max_samples=current_app.config["MAX_SAMPLES"],
    )


@bp.get("/usage")
def usage():
    return render_template(
        "usage.html",
        snippets=snippets_module,
        pygments_styles=snippets_module.styles,
        maps=services().registry.public_metadata(),
        max_samples=current_app.config["MAX_SAMPLES"],
    )


@bp.get("/privacy")
def privacy():
    return render_template(
        "privacy.html",
        retention_days=current_app.config["USAGE_RETENTION_DAYS"],
        geoip_enabled=current_app.config["GEOIP_ENABLED"],
    )


@bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "version": __version__})


@bp.get("/readyz")
def readyz():
    svc = services()
    problems = []

    try:
        with svc.db.connect() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as err:
        problems.append(f"database: {err}")

    data_dir = current_app.config["DATA_DIR"]
    if not os.path.isdir(data_dir):
        problems.append(f"data directory missing: {data_dir}")

    if not svc.registry.names():
        problems.append("no maps configured")

    if problems:
        return jsonify({"status": "error", "problems": problems}), 503

    return jsonify(
        {
            "status": "ready",
            "version": __version__,
            "maps": len(svc.registry.names()),
            "loaded": svc.registry.loaded(),
            "stamp_images": len(svc.stamps.available_maps()),
        }
    )


@bp.get("/robots.txt")
def robots():
    body = (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Crawl-delay: 1\n"
        "\n"
        "Sitemap: /sitemap.xml\n"
    )
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    base = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    pages = ["/", "/query", "/usage", "/papers", "/privacy"]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path in pages:
        body += f"  <url><loc>{base}{path}</loc></url>\n"
    body += "</urlset>\n"
    return Response(body, mimetype="application/xml")
