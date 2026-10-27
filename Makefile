ENV_NAME  := ordfi
PLATFORMS := -p osx-arm64 -p linux-64
RUN       := conda run --no-capture-output -n $(ENV_NAME)

.DEFAULT_GOAL := help
.PHONY: help env env-update lock install hooks lint format typecheck test check clean

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

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist src/*.egg-info
