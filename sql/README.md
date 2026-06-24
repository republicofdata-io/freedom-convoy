# SQL

SQL used to extract, stage, profile, and audit the GDELT observation layer.

Planned contents:

- BigQuery extraction queries for the Dec 2021–Mar 2022 window;
- cost-estimation/dry-run query variants;
- DuckDB queries for profiling coverage, sources, actors, and locations;
- evidence-table queries used by the final comparison artifact.

Queries should preserve the convoy boundary as configuration where possible rather than burying assumptions in ad hoc filters.
