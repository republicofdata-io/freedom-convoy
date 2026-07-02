"""Load the resolved tables into DuckDB and check referential integrity."""

from __future__ import annotations

import duckdb
import typer

from .settings import DUCKDB_PATH, TABLES_DIR

app = typer.Typer(help="Load rouleau parquet tables into DuckDB.")

FK_CHECKS = [
    ("protest_event", "movement_phase_id", "movement_phase", "phase_id"),
    ("protest_event", "primary_location_id", "location", "location_id"),
    ("state_response", "responding_actor_id", "actor", "actor_id"),
    ("actor_event", "actor_id", "actor", "actor_id"),
    ("actor_event", "event_id", "protest_event", "event_id"),
    ("event_location", "event_id", "protest_event", "event_id"),
    ("event_location", "location_id", "location", "location_id"),
    ("event_timeline", "event_id", "protest_event", "event_id"),
    ("event_timeline", "phase_id", "movement_phase", "phase_id"),
]


@app.command()
def run() -> None:
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS rouleau")
    for path in sorted(TABLES_DIR.glob("*.parquet")):
        table = path.stem
        con.execute(
            f"CREATE OR REPLACE TABLE rouleau.{table} AS SELECT * FROM read_parquet(?)",
            [str(path)],
        )
        n = con.execute(f"SELECT count(*) FROM rouleau.{table}").fetchone()[0]
        typer.echo(f"rouleau.{table}: {n} rows")

    orphans_total = 0
    for child, fk, parent, pk in FK_CHECKS:
        orphans = con.execute(
            f"""
            SELECT count(*) FROM rouleau.{child} c
            WHERE c.{fk} IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM rouleau.{parent} p WHERE p.{pk} = c.{fk})
            """
        ).fetchone()[0]
        if orphans:
            orphans_total += orphans
            typer.echo(f"ORPHANS: {child}.{fk} → {parent}.{pk}: {orphans}", err=True)
    con.close()

    if orphans_total:
        typer.echo(f"Referential integrity FAILED: {orphans_total} orphan rows", err=True)
        raise typer.Exit(code=1)
    typer.echo("Referential integrity: OK")


if __name__ == "__main__":
    app()
