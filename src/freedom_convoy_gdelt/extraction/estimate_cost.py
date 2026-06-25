"""Free dry-run cost estimator for GDELT extraction queries."""

from __future__ import annotations

from datetime import date as Date

import typer

from .cost_guard import bigquery_client, estimate_bytes
from .dates import configured_window, days, month_bounds, parse_day
from .queries import render_query
from .settings import QUERY_NAMES

app = typer.Typer(add_completion=False, help=__doc__)

GIB = 1024**3
TIB = 1024**4
USD_PER_TIB = 6.25


def fmt(total_bytes: int) -> str:
    return f"{total_bytes / GIB:8.2f} GiB  (~${total_bytes / TIB * USD_PER_TIB:6.3f})"


def estimate_day(client, day: Date, *, verbose: bool = False) -> int:
    total = 0
    ds = day.isoformat()
    for name in QUERY_NAMES:
        est = estimate_bytes(client, render_query(name, ds))
        total += est.bytes_processed
        if verbose:
            typer.echo(f"  {name:28s} {est.human}")
    return total


def estimate_range(client, start: Date, end: Date, label: str) -> int:
    total = 0
    n = 0
    for day in days(start, end):
        total += estimate_day(client, day)
        n += 1
    typer.echo(f"{label:14s} {n:3d} days   {fmt(total)}")
    return total


@app.command()
def main(
    date_: str | None = typer.Option(None, "--date", help="Single partition date YYYY-MM-DD"),
    month: str | None = typer.Option(None, "--month", help="One month YYYY-MM"),
    window: bool = typer.Option(False, "--window", help="Full configured window"),
) -> None:
    """Run BigQuery dry-runs only. This command bills nothing."""
    client = bigquery_client()

    if date_:
        total = estimate_day(client, parse_day(date_), verbose=True)
        typer.echo(f"  {'TOTAL':28s} {fmt(total)}")
        return

    if month:
        start, end = month_bounds(month)
        estimate_range(client, start, end, month)
        return

    if window:
        win_start, win_end = configured_window()
        typer.echo("Per-month dry-run estimate (free; nothing billed):\n")
        grand = 0
        cursor = win_start
        while cursor <= win_end:
            label = cursor.strftime("%Y-%m")
            start, end = month_bounds(label)
            grand += estimate_range(client, start, end, label)
            cursor = end.replace(day=28)
            # first day of next month
            cursor = Date(cursor.year + (cursor.month == 12), (cursor.month % 12) + 1, 1)
        typer.echo("-" * 48)
        typer.echo(f"{'FULL WINDOW':14s}         {fmt(grand)}")
        return

    typer.echo("Pass one of --date / --month / --window. See --help.", err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
