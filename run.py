#!/usr/bin/env python
"""Development server (use gunicorn in production)."""

import os

from map3d import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("MAP3D_DEBUG", "1") == "1"
    app.config["TEMPLATES_AUTO_RELOAD"] = debug
    app.run(
        debug=debug,
        host=os.environ.get("MAP3D_HOST", "127.0.0.1"),
        port=int(os.environ.get("MAP3D_PORT", "5000")),
    )
