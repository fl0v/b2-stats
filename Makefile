.PHONY: help venv install dev-install test run tray build-windows clean

.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtualenv in .venv
	python3 -m venv $(VENV)

install: venv ## Install runtime dependencies (CLI + tray)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e .

dev-install: venv ## Install runtime + dev dependencies (adds pytest)
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"

test: dev-install ## Run the test suite
	$(VENV)/bin/pytest -q

run: install ## Run the CLI (b2-stats)
	$(VENV)/bin/b2-stats

tray: install ## Run the tray app (b2-stats-tray)
	$(VENV)/bin/b2-stats-tray

build-windows: dev-install ## Build the Windows .exe (must run on Windows)
	$(PIP) install -q pyinstaller
	$(PYTHON) scripts/build_windows.py

clean: ## Remove the venv, build artifacts, and caches
	rm -rf $(VENV) build dist *.egg-info b2_stats.egg-info .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
