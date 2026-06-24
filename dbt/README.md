# dbt

Placeholder for the dbt-duckdb analytical substrate.

Minimum planned staging models:

- `stg_gdelt__gkg`
- `stg_gdelt__events`
- `stg_gdelt__mentions`

The staging layer should hide raw GDELT field weirdness behind stable analytical views and include tests for date coverage, required fields, row-count sanity, and joinability where applicable.
