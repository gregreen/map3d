"""WSGI entry point used by gunicorn."""

from map3d import create_app

app = create_app()
application = app
