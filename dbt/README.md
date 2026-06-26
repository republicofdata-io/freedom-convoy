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

## Layering and transformation strategy

This project uses dbt as the data pipeline framework. The useful lesson from DuckDB-style analytical pipelines is not to replace dbt with a Python pipeline, but to keep each transformation explicit, named, composable, and testable.

The working layer model is:

| Layer | Role in this experiment |
|---|---|
| Raw / landing | Local partitioned GDELT Parquet extracts; preserve source traces with minimal interpretation. |
| Bronze | Staged, typed, queryable GDELT records with stable names, dates, keys, URLs, and source fields. |
| Silver | Observation-layer business logic: convoy boundary semantics, source normalization, week/phase buckets, actor/location extraction, and trace-preserving observation concepts. |
| Gold | Facts, dimensions, and extended aggregates that can support cited claims: coverage facts, source/actor/location dimensions, weekly coverage, source concentration, amplification, event-code mix, and evidence summaries. |
| Artifact | Marimo comparison app, scorecard, transcripts, and strategic readout. |

The project should avoid collapsing these steps into one large query or notebook. dbt models should make the transition from staged records to semantic observation records to citeable evidence products inspectable in the DAG.

A useful shorthand for the experiment is:

```text
GDELT traces
→ Bronze staged records
→ Silver observation-layer semantics
→ Gold evidence facts/dimensions/aggregates
→ grounded claims in the artifact
```

Gold models should produce evidence, not overstate interpretation. For example, `top_source_share = 0.62` is evidence; `the movement was dominated by that source's perspective` is a claim that must be argued and cited in the artifact.

## Testing strategy

The staging layer currently includes basic tests for:

- required fields via `not_null`;
- uniqueness where applicable;
- minimum row-count sanity;
- date coverage across the target extraction window;
- mention-to-event joinability.

As the project adds Silver and Gold models, tests should follow the layer where the logic lives:

| Layer | Test focus | dbt mechanism |
|---|---|---|
| Raw / landing | Expected files/date partitions are present and readable. | Make/script checks outside dbt, or lightweight source-read tests. |
| Bronze | Staged records are valid, typed, keyed, and stable. | Generic and singular dbt tests. |
| Silver | Business/semantic logic behaves as intended on small examples. | dbt unit tests written as scenario-style fixtures. |
| Gold | Facts, dimensions, and aggregates calculate evidence correctly. | dbt unit tests plus singular invariant tests. |
| Artifact | Claims cite real evidence and do not treat observations as ground truth. | Scorecard/claim validation outside dbt, with references back to Gold evidence. |

### Gherkin-style scenario discipline

The novel testing lesson for this experiment is to use Gherkin-style scenarios as a design and testing discipline for analytical transformations:

```gherkin
Given a small set of observation records
When a semantic or aggregate transformation is applied
Then the resulting evidence rows should match the expected interpretation
```

There is no need to introduce a separate Gherkin package by default. In dbt, these scenarios should usually be implemented as native dbt unit tests with `given` input rows and `expect` output rows, with scenario-like names and descriptions.

Good candidates for scenario-style dbt unit tests include:

- convoy boundary matching includes relevant records and excludes unrelated logistics records;
- source normalization collapses common aliases before concentration is calculated;
- observation dates map to the expected week or movement phase;
- weekly coverage aggregates count records and unique sources correctly;
- source concentration calculates `top_source_share`, top-N share, and concentration flags correctly;
- actor/location amplification calculates mention shares and ranks correctly;
- evidence models preserve trace fields needed for drill-through and grounded claims.

Example scenario, expressed conceptually:

```gherkin
Scenario: Source concentration identifies a dominated observation window
  Given weekly document observations from CBC, BBC, and Reuters
  When source concentration is calculated
  Then the top source is CBC
  And top_source_share equals CBC observations divided by total observations
```

The same scenario can be expressed in dbt as a unit test against the Gold source-concentration model. This keeps the pipeline dbt-native while preserving the readability and intent of Given/When/Then analytical tests.
