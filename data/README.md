# Data

Local data outputs live here during extraction and analysis, but raw and large derived files are not committed.

Planned local layout:

```text
data/parquet/      Partitioned GDELT extracts generated from BigQuery
data/raw/          Optional raw scratch outputs
data/processed/    Optional derived tables exported from DuckDB/dbt/Marimo
```

Target extraction window: `2021-12-01` through `2022-03-31`.

Expected GDELT surfaces:

- GKG documents / article metadata;
- Events;
- Mentions.

Ticket 02 will add cost-guarded extraction commands, query versions, and extraction logs. Keep credentials, local database files, and regenerated data out of Git.
