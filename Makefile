ENV_NAME  := ordfi
PLATFORMS := -p osx-arm64 -p linux-64
RUN       := conda run --no-capture-output -n $(ENV_NAME)
ORDFI_DATA_DIR ?= $(CURDIR)/data
DBT        = ORDFI_DATA_DIR=$(ORDFI_DATA_DIR) $(RUN) dbt
# Direct interpreter path, so background processes get a real PID (not a `conda run` wrapper).
PYTHON     = $(shell conda run -n $(ENV_NAME) python -c "import sys; print(sys.executable)")

.DEFAULT_GOAL := help
.PHONY: help env env-update lock install hooks lint format typecheck test check clean \
        ingest-bts ingest-atcscc ingest-iem dbt-build features backtest dagster \
        collector-start collector-stop collector-status

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

env: ## Create the conda environment from environment.yml
	conda env create -f environment.yml

env-update: ## Sync the environment with environment.yml
	conda env update -n $(ENV_NAME) -f environment.yml --prune

lock: ## Regenerate conda-lock.yml (osx-arm64, linux-64; CPU-only builds)
	$(RUN) conda-lock lock -f environment.yml $(PLATFORMS) --without-cuda

install: ## Editable install of the ordfi package
	$(RUN) python -m pip install -e . --no-deps

hooks: ## Install pre-commit git hooks
	$(RUN) pre-commit install

lint: ## Lint and check formatting
	$(RUN) ruff check .
	$(RUN) ruff format --check .

format: ## Auto-format and apply safe lint fixes
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck: ## Static type-check (mypy --strict)
	$(RUN) mypy

test: ## Run the test suite with coverage
	$(RUN) pytest --cov --cov-report=term-missing

check: lint typecheck test ## Everything CI runs

ingest-bts: ## Fetch + stage BTS months: TABLE=marketing FROM=2018-01 TO=2026-08 (or MONTH=)
	$(RUN) python -m ordfi.ingest.bts --table $(or $(TABLE),marketing) \
		$(if $(MONTH),--month $(MONTH),--from $(FROM) --to $(TO))

ingest-atcscc: ## Crawl + stage ATCSCC advisories: FROM=2015-01-01 TO=2026-10-26 (defaults: 2001 → yesterday)
	$(RUN) python -m ordfi.ingest.atcscc $(if $(FROM),--from $(FROM)) $(if $(TO),--to $(TO))

ingest-iem: ## Fetch + stage IEM METAR/TAF for ORD: FROM=2015-01 TO=2026-10 (defaults: 2000-01 → this month)
	$(RUN) python -m ordfi.ingest.iem $(if $(FROM),--from $(FROM)) $(if $(TO),--to $(TO))

dbt-build: ## Build and test the dbt core models (Parquet in data/core): SELECT=flight_leg+ to limit
	mkdir -p $(ORDFI_DATA_DIR)/core $(ORDFI_DATA_DIR)/warehouse
	$(DBT) build --project-dir dbt --profiles-dir dbt $(if $(SELECT),--select $(SELECT))

features: ## Build as-of feature snapshots from data/core: SPINE=departures|hours FROM=2019-01 TO=2019-12 (HORIZONS=24h,6h,...)
	ORDFI_DATA_DIR=$(ORDFI_DATA_DIR) $(RUN) python -m ordfi.features --spine $(or $(SPINE),departures) \
		--from $(FROM) --to $(TO) $(if $(HORIZONS),--horizons $(HORIZONS))

backtest: ## Rolling-origin backtest: TASK=all|hour_bad60|... FROM=2024-09 TO=2026-08 (MODELS=calendar,gbdt WORKERS=n NAME=run-name)
	ORDFI_DATA_DIR=$(ORDFI_DATA_DIR) $(RUN) python -m ordfi.models.backtest --task $(or $(TASK),all) \
		--from $(FROM) --to $(TO) $(if $(HORIZONS),--horizons $(HORIZONS)) $(if $(MODELS),--models $(MODELS)) \
		$(if $(WORKERS),--workers $(WORKERS)) $(if $(NAME),--run $(NAME))

dagster: ## Start the local Dagster UI (http://127.0.0.1:3000)
	mkdir -p .dagster && touch .dagster/dagster.yaml
	DAGSTER_HOME=$(CURDIR)/.dagster $(RUN) dagster dev -f pipelines/definitions.py

collector-start: ## Start the live collector in the background (log: data/logs/collector.log)
	@mkdir -p data/logs
	@nohup $(PYTHON) -m ordfi.collector >> data/logs/collector.log 2>&1 &
	@sleep 5 && $(PYTHON) -m ordfi.collector --status

collector-stop: ## Stop the live collector
	@$(PYTHON) -m ordfi.collector --stop

collector-status: ## Show live collector status and today's poll counts
	@$(PYTHON) -m ordfi.collector --status

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist src/*.egg-info \
		dbt/target dbt/logs
