# Marimo

Marimo apps for interactive inspection and final presentation.

## Observation-layer profiling

Run the DuckDB/dbt build, then open the profiling app:

```bash
make dbt-build
make marimo-observation
```

App:

- `marimo/observation_layer_profile.py`

The app profiles GDELT as an observation layer, not ground truth:

- weekly coverage volume;
- event vs mention volume;
- source concentration;
- location distribution;
- Ottawa vs border-blockade coverage;
- actor/source amplification;
- coverage lead/lag patterns;
- obvious gaps, ambiguities, and low-confidence areas.

Use the app's **Export summary CSVs** button, or run the non-interactive export command, to persist measured facts to:

```bash
make observation-summaries
```

```text
data/derived/observation_layer/
```

Those CSVs are local derived artifacts for later scoring and the final comparison app.

## Planned final artifact

A final comparison artifact with side-by-side condition outputs, embedded scorecard, evidence traces, and strategic readout will be added later.

The final shipped experience should be DuckDB-backed and measured from data, not static illustrative mockups.
