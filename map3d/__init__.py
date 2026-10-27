from __future__ import annotations

import logging
import uuid
from typing import Any

from astropy import units as u
from astropy.coordinates import SkyCoord
from dustmaps import json_serializers
from flask import Flask, Response, current_app, g, jsonify, request
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix

from .cli import register_cli
from .config import default_config
from .logging_setup import configure_logging
from .services import Services, build_services

__version__ = "2.0.0"

log = logging.getLogger(__name__)


class DustMapsJSONProvider(DefaultJSONProvider):
    """JSON provider that emits dustmaps' array/Quantity/SkyCoord encoding.

    ``dustmaps.bayestar.BayestarWebQuery`` decodes responses with
    ``json_serializers.MultiJSONDecoder``, so the wire format must not change.
    """

    @staticmethod
    def default(o: Any):
        import numpy as np

        if isinstance(o, SkyCoord):
            return json_serializers.serialize_skycoord(o)
        if isinstance(o, u.Quantity):
            return json_serializers.serialize_quantity(o)
        if isinstance(o, np.ndarray):
            return json_serializers.serialize_ndarray_b64(o)
        if isinstance(o, np.dtype):
            return json_serializers.serialize_dtype(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.void):
            try:
                return json_serializers.serialize_ndarray_b64(np.array(o))
            except Exception:
                pass
        return DefaultJSONProvider.default(o)


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(default_config())
    if config:
        app.config.update(config)

    configure_logging(app.config["LOG_LEVEL"])
    app.json = DustMapsJSONProvider(app)

    hops = int(app.config.get("TRUSTED_PROXY_HOPS") or 0)
    if hops:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_port=hops
        )

    from flask_compress import Compress

    Compress(app)

    app.extensions["map3d"] = build_services(app.config)

    from .views import api_v2, interactive, legacy, pages

    app.register_blueprint(pages.bp)
    app.register_blueprint(api_v2.bp)
    app.register_blueprint(interactive.bp)
    if app.config.get("ENABLE_LEGACY_API", True):
        app.register_blueprint(legacy.bp)

    register_cli(app)
    _register_request_hooks(app)
    _register_error_handlers(app)

    log.info(
        "app ready maps=%d images=%d data_dir=%s",
        len(app.extensions["map3d"].registry.names()),
        len(app.extensions["map3d"].stamps.available_maps()),
        app.config["DATA_DIR"],
    )
    return app


def services() -> Services:
    return current_app.extensions["map3d"]


def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        g.rate_limit = None
        g.args = {}

    @app.after_request
    def _augment_response(response: Response):
        response.headers.setdefault("X-Request-ID", getattr(g, "request_id", ""))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

        limit = getattr(g, "rate_limit", None)
        if limit is not None:
            response.headers["X-RateLimit-Limit"] = str(limit.limit)
            response.headers["X-RateLimit-Remaining"] = str(limit.remaining)
            response.headers["X-RateLimit-Work-Limit"] = str(limit.work_limit)
            response.headers["X-RateLimit-Work-Remaining"] = str(limit.work_remaining)
            response.headers["X-RateLimit-Reset"] = str(limit.reset)
            if not limit.allowed:
                response.headers["Retry-After"] = str(limit.retry_after)
        return response


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _register_error_handlers(app: Flask) -> None:
    def error(message: str, status: int):
        if _wants_json():
            return (
                jsonify({"error": message, "request_id": getattr(g, "request_id", "")}),
                status,
            )
        return Response(message + "\n", status=status, mimetype="text/plain")

    @app.errorhandler(400)
    def _bad_request(err):
        return error(getattr(err, "description", "Bad request."), 400)

    @app.errorhandler(404)
    def _not_found(err):
        return error("Not found.", 404)

    @app.errorhandler(405)
    def _not_allowed(err):
        return error("Method not allowed.", 405)

    @app.errorhandler(413)
    def _too_large(err):
        return error("Request body too large.", 413)

    @app.errorhandler(500)
    def _server_error(err):
        log.exception("unhandled error request_id=%s", getattr(g, "request_id", ""))
        return error(
            "Internal server error. Quote request id {} when reporting.".format(
                getattr(g, "request_id", "")
            ),
            500,
        )
