.DEFAULT_GOAL := help

.PHONY: help install cost-day cost-month cost-window backfill-day backfill-month backfill-range backfill-window dbt-build dbt-test dbt-docs-generate duckdb-ui marimo-observation observation-summaries rouleau-corpus rouleau-extract rouleau-extract-chapter rouleau-verify rouleau-resolve rouleau-load rouleau-sample

help: ## Show this menu
	@echo "Freedom Convoy GDELT extraction commands:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create/update the uv environment
	uv sync

cost-day: ## Free dry-run estimate for one day: DATE=2022-02-14
	uv run python scripts/estimate_cost.py --date $(DATE)

cost-month: ## Free dry-run estimate for one month: MONTH=2022-02
	uv run python scripts/estimate_cost.py --month $(MONTH)

cost-window: ## Free dry-run estimate for full extraction window
	uv run python scripts/estimate_cost.py --window

backfill-day: ## BILLED: extract one day: DATE=2022-02-14
	uv run python scripts/backfill.py --date $(DATE)

backfill-month: ## BILLED: extract one month: MONTH=2022-02
	uv run python scripts/backfill.py --month $(MONTH)

backfill-range: ## BILLED: extract range: START=2022-02-01 END=2022-02-07
	uv run python scripts/backfill.py --start $(START) --end $(END)

backfill-window: ## BILLED: extract full window
	uv run python scripts/backfill.py --window

dbt-build: ## Build DuckDB/dbt staging layer
	uv run dbt build --project-dir dbt --profiles-dir dbt

dbt-test: ## Run dbt tests only
	uv run dbt test --project-dir dbt --profiles-dir dbt

dbt-docs-generate: ## Generate dbt docs metadata
	uv run dbt docs generate --project-dir dbt --profiles-dir dbt

duckdb-ui: ## Open DuckDB UI for the local staged database; keep this terminal open
	uv run duckdb -ui -interactive data/freedom_convoy.duckdb

marimo-observation: ## Run the observation-layer profiling Marimo app
	uv run marimo edit marimo/observation_layer_profile.py

observation-summaries: ## Export observation-layer summary CSVs for scoring/final artifact
	uv run python scripts/export_observation_summaries.py

rouleau-corpus: ## Build page-anchored text corpus from the Rouleau report PDFs
	uv run python -m freedom_convoy_rouleau.corpus

rouleau-extract: ## BILLED: extract facts from all in-scope report pages (OpenRouter)
	uv run python -m freedom_convoy_rouleau.extract

rouleau-extract-chapter: ## BILLED: extract one chapter: CHAPTER=10
	uv run python -m freedom_convoy_rouleau.extract --chapter $(CHAPTER)

rouleau-verify: ## Verify every record's source_quote against the cited page
	uv run python -m freedom_convoy_rouleau.verify run

rouleau-resolve: ## Resolve entities and build semantic-model parquet tables
	uv run python -m freedom_convoy_rouleau.resolve

rouleau-load: ## Load rouleau tables into DuckDB + referential integrity checks
	uv run python -m freedom_convoy_rouleau.load

rouleau-sample: ## Draw stratified human spot-check sample CSV
	uv run python -m freedom_convoy_rouleau.verify sample
