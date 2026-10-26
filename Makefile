PYTHON ?= .venv/bin/python
PIP ?= $(PYTHON) -m pip
COMPOSE := docker compose -f docker/docker-compose.yml

.PHONY: help venv install test lint fmt run data images geoip docker-build docker-up docker-down clean

help:
	@echo "Targets:"
	@echo "  venv          create .venv (Python 3)"
	@echo "  install       install dependencies into .venv (incl. dustmaps from GitHub)"
	@echo "  test          run the test suite"
	@echo "  lint          ruff check"
	@echo "  fmt           ruff format"
	@echo "  run           run the development server on :5000"
	@echo "  data          download any missing maps (no-op if present)"
	@echo "  images        build missing postage-stamp image caches"
	@echo "  geoip         download the DB-IP Lite city database"
	@echo "  docker-build  build the container image"
	@echo "  docker-up     start the stack with docker compose"
	@echo "  docker-down   stop the stack"

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install pytest ruff
	$(PIP) install -e .
	$(PIP) install -e ../dustmaps || $(PIP) install "dustmaps @ git+https://github.com/gregreen/dustmaps@master"

test:
	$(PYTHON) -m pytest -q -m "not live"

lint:
	$(PYTHON) -m ruff check map3d tests scripts

fmt:
	$(PYTHON) -m ruff format map3d tests scripts

run:
	$(PYTHON) run.py

data:
	$(PYTHON) scripts/fetch_maps.py --all --report

images:
	$(PYTHON) scripts/build_stamp_images.py --all

geoip:
	$(PYTHON) scripts/update_geoip.py

docker-build:
	docker build -f docker/Dockerfile -t map3d:latest .

docker-up:
	test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build

docker-down:
	$(COMPOSE) down

clean:
	rm -rf .pytest_cache **/__pycache__ var
