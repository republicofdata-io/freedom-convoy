# Freedom Convoy: Reconstructing the Observation Layer

> An AI-readiness experiment about the gap between a phenomenon and its recorded traces. GDELT's coverage of the 2022 Freedom Convoy is used as a public, checkable proxy for a broader data problem: agents can ground answers in real records and still mistake the observation layer for reality.

## Core thesis

**GDELT is an observation layer, not ground truth.**

GDELT does not contain the Freedom Convoy. It contains traces of how the convoy was observed, reported, encoded, and amplified by news sources and event-coding infrastructure. Record counts, article volume, source concentration, locations, and coded events are evidence — but they are not the phenomenon itself.

This experiment asks whether an AI analyst can characterize that lens: where the observation layer over-represents, under-represents, distorts, or misses the underlying phenomenon.

## What this experiment measures

This is **not** primarily a factual-recovery task. A frontier model may already know many facts about the Freedom Convoy from training data. That makes simple reconstruction a weak test.

Instead, the experiment measures **lens-bias characterization**:

- What did GDELT record?
- How did coverage volume, source mix, actor mentions, and locations behave over time?
- Where did recorded attention diverge from on-the-ground significance?
- Can the agent distinguish media amplification from movement importance?
- Can every distortion claim be grounded in cited traces from the data?

The central scoring rule is the **groundedness gate**: a distortion claim must cite supporting traces such as counts, coverage curves, source mix, or query outputs. Unsupported claims score zero for groundedness, even if they are true.

## Four experimental conditions

All conditions use the same model family/capability level. What changes is the support given for reasoning about the lens.

1. **Parametric-only** — no data. Establishes what the model says from memory and what it cannot ground about the GDELT observation layer.
2. **Raw-data** — access to raw/staged GDELT records and neutral schema documentation only.
3. **Semantic** — raw data plus lens-oriented concepts such as observer, source, media amplification, coverage bias, narrative, movement phase, and evidence confidence.
4. **Evaluated** — semantic condition plus explicit requirements for groundedness, uncertainty, traceability, and cited distortion claims.

The hypothesis: lens-describing semantics and evaluation pressure help an agent reason like an experienced analyst — treating records as biased traces, not as reality itself.

## Hero questions

The benchmark focuses on questions that expose the gap between the phenomenon and the lens:

- How did coverage volume evolve week by week, and where did it spike independent of on-the-ground activity?
- Which actors and locations were most amplified, and did amplification track significance or diverge from it?
- What sources dominated the narrative, and what coverage bias does that introduce?
- Where did the observation layer reflect known events proportionally, and where did it distort, inflate, or miss them?

## Core deliverable

The shipped artifact is a **DuckDB-backed Marimo comparison app** with an embedded scorecard.

A reader should be able to see, side by side, how a raw-data agent can sound authoritative while treating coverage as reality, and how a semantic/evaluated agent reasons about GDELT as a biased observation layer.

The final artifact should include:

- side-by-side condition outputs;
- scorecard results across conditions;
- evidence traces behind scores;
- coverage-over-time views;
- source concentration views;
- actor/location amplification views;
- a strategic readout connecting the result to enterprise data and agentic BI.

## Why this matters beyond GDELT

Enterprise warehouses are also observation layers. Tickets, transactions, CRM updates, logs, product events, and metrics are engineered traces of a business — not the business itself.

An agent that reads those records correctly can still produce a confident distortion if it mistakes instrumentation for reality:

| GDELT lens | Enterprise lens |
|---|---|
| Coverage volume does not equal event importance | Record count does not equal business importance |
| Source concentration shapes the narrative | System/instrumentation concentration shapes the warehouse |
| Media spikes can diverge from activity | Metric spikes can reflect tracking changes |
| Observer/source bias affects records | Definitions and modeling choices affect metrics |
| Missing traces are not proof of absence | Uninstrumented business reality remains invisible |

The broader claim: **grounding makes an answer defensible; experience makes it trustworthy.** A semantic layer should encode enough lens knowledge to help agents reason about what the data can and cannot support.

## Repository layout

```text
artifact/      Final comparison artifact code and supporting assets
data/          Data notes and local output locations; raw/large data is not committed
dbt/           dbt-duckdb project scaffold for staged analytical models
evaluation/    Benchmark, oracle separation notes, rubric, and scorecards
marimo/        Marimo profiling and comparison apps
prompts/       Condition prompt packs and transcript templates
sql/           BigQuery/DuckDB SQL used for extraction, profiling, and evidence tables
transcripts/   Manual run transcripts and run metadata
```

## Data and reproducibility posture

Raw and derived GDELT data are intentionally excluded from Git. The target extraction window is `2021-12-01` through `2022-03-31`, covering buildup, Ottawa occupation, border blockades, emergency response, clearance, and immediate aftermath.

Ticket 02 adds a `uv`-managed extraction substrate with Make commands:

```bash
make help
make install
make cost-day DATE=2022-02-14
make cost-month MONTH=2022-02
make cost-window
make backfill-day DATE=2022-02-14
make backfill-month MONTH=2022-02
make backfill-range START=2022-02-01 END=2022-02-07
make backfill-window
```

The `cost-*` commands are free BigQuery dry runs. The `backfill-*` commands are billed and should be run only after reviewing dry-run estimates. Outputs are local, gitignored Parquet partitions under `data/parquet/raw/`, with extraction logs under `data/logs/`. The convoy-candidate boundary is configured in `config/gdelt_candidate.yaml`.

Later tickets will add reproducible commands for:

- DuckDB/dbt staging;
- Marimo profiling;
- final comparison artifact generation.

## Rouleau Commission facts database (ground truth)

The experiment's ground-truth oracle is built from the factual-narrative
chapters of the Public Order Emergency Commission (Rouleau Commission) final
report — Vol 2 Ch 5–13 and Vol 3 Ch 14–16 (~470 evidentiary pages). The
Commissioner's findings (Vol 3 Ch 17) and recommendations (Ch 18) are excluded
by construction, as are Vols 1, 4, and 5.

Pipeline (`src/freedom_convoy_rouleau/`, config in `config/rouleau_*.yaml`):

```bash
make rouleau-corpus            # page-anchored text corpus from the report PDFs
make rouleau-extract           # BILLED: LLM extraction (OpenRouter; see .env.example)
make rouleau-verify            # 100% source_quote-vs-page citation verification
make rouleau-resolve           # entity resolution → semantic-model parquet tables
make rouleau-load              # load into DuckDB (rouleau schema) + FK checks
make rouleau-sample            # stratified sample CSV for human spot-checking
```

Key properties:

- **Citations are pipeline metadata, never model output.** Extraction runs one
  page at a time; volume/chapter/page are stapled on afterwards. Every record
  carries a verbatim `source_quote` that is automatically verified as a
  substring of the cited page; failures are quarantined, not shipped.
- **Evidentiary-only via three layers:** chapter scoping, prompt instruction,
  and a conclusion-marker QA scan.
- **GDELT-joinable, not GDELT-keyed:** locations carry lat/long + FIPS ADM1
  codes and actors a CAMEO type crosswalk; the join is date + geography
  alignment (see `sql/rouleau_gdelt_join.sql`).

The report PDFs are downloaded to `data/raw/rouleau/` (gitignored); SHA-256
checksums are committed in `config/rouleau_checksums.sha256` for verification.

## What this project does not claim

- It does not take a political position on the Freedom Convoy.
- It does not treat GDELT as ground truth.
- It does not treat article, mention, or event volume as event importance.
- It does not claim semantics replace human judgment.
- It does not score unsupported claims as grounded merely because they are plausible or true.

## Current status

Ticket 01 establishes the release framing and repository structure. Subsequent tickets will build the extraction substrate, DuckDB/dbt staging layer, profiling apps, benchmark, prompt packs, scoring apparatus, comparison artifact, and strategic readout.
