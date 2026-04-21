PYTHON ?= python3

.PHONY: format format-check spec-fetch spec-fix spec-validate generate-models lint typecheck unit-tests tests test venv
.DEFAULT_GOAL := help

format: ## Format source files with black
	uv run black omada_client tests tools

format-check: ## Check formatting with black
	uv run black --check --diff omada_client tests tools

spec-fetch: ## Fetch raw Omada OpenAPI spec
	uv run $(PYTHON) tools/fetch_spec.py

spec-fix: ## Patch and normalize OpenAPI spec
	uv run $(PYTHON) tools/fix_spec.py

spec-validate: ## Validate patched OpenAPI spec
	uv run $(PYTHON) tools/validate_spec.py

generate-models: ## Generate internal models from spec
	uv run $(PYTHON) tools/generate_models.py

lint: format-check ## Run flake8 lint checks
	uv run flake8 omada_client tests tools

typecheck: ## Run mypy type checks
	uv run mypy omada_client

unit-tests: ## Run unit tests
	uv run pytest

tests: lint typecheck unit-tests ## Run all tests

test: tests ## Alias for tests

venv: ## Create venv and sync dev dependencies
	test -d .venv || uv venv
	uv sync --extra dev

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'
