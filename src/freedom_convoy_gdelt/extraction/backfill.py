"""Billed GDELT extraction backfill to local partitioned Parquet."""

from __future__ import annotations

from collections import defaultdict
from datetime import date as Date

import typer

from .dates import configured_window, days, month_bounds, parse_day, validate_range
from .extract import log_failure, run_layer
from .settings import LAYERS, data_dir, log_dir

app = typer.Typer(add_completion=False, help=__doc__)


def run_range(start: Date, end: Date, *, override_ceiling: bool = False) -> None:
    typer.echo("BILLED BigQuery extraction")
    typer.echo(f"Window: {start.isoformat()} -> {end.isoformat()}")
    typer.echo(f"Output: {data_dir() / 'raw'}")
    typer.echo(f"Log:    {log_dir() / 'extraction_runs.jsonl'}\n")

    total_rows = 0
    total_cost = 0.0
    failures: list[tuple[str, str]] = []
    by_layer = defaultdict(int)

    for day in days(start, end):
        ds = day.isoformat()
        day_rows = 0
        day_cost = 0.0
        for layer in LAYERS:
            try:
                record = run_layer(layer, ds, override_ceiling=override_ceiling)
                rows = int(record["rows"])
                cost = float(record["est_cost_usd"])
                day_rows += rows
                day_cost += cost
                by_layer[layer] += rows
                typer.echo(f"{ds}  {layer:15s} ok     rows={rows:<7} ~${cost:.4f}")
            except Exception as exc:  # noqa: BLE001 - log and continue to next layer
                failures.append((ds, layer))
                log_failure(layer, ds, exc)
                typer.echo(f"{ds}  {layer:15s} FAIL   {type(exc).__name__}: {exc}")
        total_rows += day_rows
        total_cost += day_cost
        typer.echo(f"{ds}  {'DAY TOTAL':15s}        rows={day_rows:<7} ~${day_cost:.4f}\n")

    typer.echo("DONE")
    typer.echo(f"Rows:       {total_rows}")
    typer.echo(f"Est. cost:  ~${total_cost:.4f}")
    typer.echo(f"Failures:   {len(failures)}")
    for layer, rows in sorted(by_layer.items()):
        typer.echo(f"  {layer:15s} {rows}")
    if failures:
        typer.echo(f"Failed partitions/layers: {failures}")
        raise typer.Exit(code=1)


@app.command()
def main(
    date_: str | None = typer.Option(None, "--date", help="Single partition date YYYY-MM-DD"),
    month: str | None = typer.Option(None, "--month", help="One month YYYY-MM"),
    start: str | None = typer.Option(None, "--start", help="Range start YYYY-MM-DD"),
    end: str | None = typer.Option(None, "--end", help="Range end YYYY-MM-DD"),
    window: bool = typer.Option(False, "--window", help="Full configured window"),
    override_ceiling: bool = typer.Option(False, "--override-ceiling", help="Allow queries over BQ_MAX_SCAN_GIB after dry-run review"),
) -> None:
    """Run billed extraction. Use `make cost-*` first."""
    try:
        if date_:
            day = parse_day(date_)
            range_start, range_end = validate_range(day, day)
        elif month:
            range_start, range_end = month_bounds(month)
        elif start and end:
            range_start, range_end = validate_range(parse_day(start), parse_day(end))
        elif window:
            range_start, range_end = configured_window()
        else:
            typer.echo("Pass --date, --month, --start/--end, or --window. See --help.", err=True)
            raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Invalid extraction range: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    run_range(range_start, range_end, override_ceiling=override_ceiling)


if __name__ == "__main__":
    app()
