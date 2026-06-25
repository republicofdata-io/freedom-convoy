# dbt

DuckDB/dbt analytical substrate for local GDELT Parquet extracts.

## Commands

From the repository root:

```bash
make install
make dbt-build
make dbt-test
make duckdb-ui
```

`make dbt-build` runs `dbt build` with the project-local profile in `dbt/profiles.yml` and writes the local DuckDB database to:

```text
data/freedom_convoy.duckdb
```

Raw and derived database files are local artifacts and should not be committed.

`make duckdb-ui` opens DuckDB's browser UI against `data/freedom_convoy.duckdb`. Keep the terminal running while using the UI; closing it stops the local server.

## Inputs

The raw read layer expects partitioned Parquet files under:

```text
data/parquet/raw/gdelt_gkg/event_date=YYYY-MM-DD/*.parquet
data/parquet/raw/gdelt_events/event_date=YYYY-MM-DD/*.parquet
data/parquet/raw/gdelt_mentions/event_date=YYYY-MM-DD/*.parquet
```

## Models

Raw Parquet views:

- `main_raw.raw_gdelt__gkg`
- `main_raw.raw_gdelt__events`
- `main_raw.raw_gdelt__mentions`

Stable staging views:

- `main_staging.stg_gdelt__gkg`
- `main_staging.stg_gdelt__events`
- `main_staging.stg_gdelt__mentions`

These staging views normalize names/types, expose stable domains and dates, keep GDELT pipe/comma-encoded fields as explicit `*_raw` columns, and add a recall-oriented `matches_convoy_boundary` helper flag.

## Boundary seed

`seeds/movement_boundary.csv` records the convoy-candidate matching terms used as a transparent, configurable boundary. The staging models use these seed patterns to populate `matches_convoy_boundary`. It is not a claim about the true movement boundary.

## Tests

The staging layer includes basic tests for:

- required fields via `not_null`;
- uniqueness where applicable;
- minimum row-count sanity;
- date coverage across the target extraction window;
- mention-to-event joinability.
