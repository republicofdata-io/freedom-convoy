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

## Extraction commands

Ticket 02 adds a lightweight `uv`-managed extraction substrate.

Install dependencies:

```bash
uv sync
```

Free dry-run cost estimates, billed nothing:

```bash
make cost-day DATE=2022-02-14
make cost-month MONTH=2022-02
make cost-window
```

Billed backfills, run only after reviewing the dry-run estimates:

```bash
make backfill-day DATE=2022-02-14
make backfill-month MONTH=2022-02
make backfill-range START=2022-02-01 END=2022-02-07
make backfill-window
```

Configuration lives in `config/gdelt_candidate.yaml`. The extraction boundary is recall-oriented and should not be treated as the movement truth boundary.

Outputs:

```text
data/parquet/raw/gdelt_gkg/event_date=YYYY-MM-DD/*.parquet
data/parquet/raw/gdelt_events/event_date=YYYY-MM-DD/*.parquet
data/parquet/raw/gdelt_mentions/event_date=YYYY-MM-DD/*.parquet
data/logs/extraction_runs.jsonl
```

Set `BIGQUERY_PROJECT_ID` and auth via `.env` or your shell. Keep credentials, local database files, extraction logs, and regenerated data out of Git.
