# syntax=docker/dockerfile:1
#
# Runtime image for the Argonaut dust-map service.
#
# Map data is *not* baked into the image: it lives on a persistent volume mounted
# at /data, so rebuilding or redeploying the image never re-downloads maps.
#
# Build (multi-arch):
#   docker buildx build --platform linux/arm64 -f docker/Dockerfile -t map3d .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libgomp1 is needed by the numpy/scipy wheels; curl by the healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# dustmaps from GitHub master. Pinning to a SHA is a deliberate follow-up.
ARG DUSTMAPS_REF=master
RUN pip install --no-cache-dir \
      "dustmaps @ git+https://github.com/gregreen/dustmaps@${DUSTMAPS_REF}"

COPY map3d ./map3d
COPY scripts ./scripts
COPY wsgi.py pyproject.toml README.md ./

RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /var/lib/map3d \
 && chown -R app:app /var/lib/map3d

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# No --preload: HDF5/FITS handles must be opened *after* the worker forks.
# gunicorn's own access log is disabled; the app emits one structured record per
# query (without client IPs).
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--threads", "2", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--error-logfile", "-", \
     "wsgi:app"]
