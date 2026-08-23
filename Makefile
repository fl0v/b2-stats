.PHONY: help install dev-install test run tray build-windows clean

.DEFAULT_GOAL := help

help: ## Show this list of commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv (via uv) and install runtime deps (CLI + tray)
	uv sync

dev-install: ## Same, plus pytest
	uv sync --extra dev

test: dev-install ## Run the test suite
	uv run pytest -q

run: install ## Run the CLI (b2-stats)
	uv run b2-stats

tray: install ## Run the tray app (b2-stats-tray)
	uv run b2-stats-tray

build-windows: ## Build the Windows .exe (must run on Windows)
	uv sync --extra build
	uv run python scripts/build_windows.py

clean: ## Remove the venv, build artifacts, and caches
	rm -rf .venv build dist *.egg-info b2_stats.egg-info .pytest_cache
	find . -name "__pycache__" -type d -exec rm -rf {} +
