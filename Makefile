.PHONY: venv install dev-install test run tray build-windows clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e .

dev-install: venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"

test: dev-install
	$(VENV)/bin/pytest -q

run: install
	$(VENV)/bin/b2-stats

tray: install
	$(VENV)/bin/b2-stats-tray

build-windows: dev-install
	$(PIP) install -q pyinstaller
	$(PYTHON) scripts/build_windows.py

clean:
	rm -rf $(VENV) build dist *.egg-info b2_stats.egg-info .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
