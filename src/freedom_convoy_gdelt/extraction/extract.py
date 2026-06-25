"""Run one cost-guarded extraction partition and write local Parquet."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .cost_guard import bigquery_client, guarded_query
from .queries import render_query
from .settings import LAYERS, CONFIG_PATH, data_dir, log_dir


def partition_dir(layer: str, partition_date: str) -> Path:
    return data_dir() / "raw" / layer / f"event_date={partition_date}"


def query_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


def append_log(record: dict[str, Any]) -> None:
    log_dir().mkdir(parents=True, exist_ok=True)
    path = log_dir() / "extraction_runs.jsonl"
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")


def run_layer(layer: str, partition_date: str, *, override_ceiling: bool = False) -> dict[str, Any]:
    query_name = LAYERS[layer]
    sql = render_query(query_name, partition_date)
    result, estimate = guarded_query(
        bigquery_client(), sql, override_ceiling=override_ceiling
    )
    table = result.to_arrow(create_bqstorage_client=False)

    out_dir = partition_dir(layer, partition_date)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{partition_date}.parquet"
    pq.write_table(table, out_file)

    record = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "layer": layer,
        "query_name": query_name,
        "partition_date": partition_date,
        "rows": table.num_rows,
        "scanned_bytes": estimate.bytes_processed,
        "scanned_gib": round(estimate.gib, 6),
        "est_cost_usd": round(estimate.usd, 6),
        "query_hash": query_hash(sql),
        "config_path": str(CONFIG_PATH.relative_to(CONFIG_PATH.parents[1])),
        "output_path": str(out_file),
    }
    append_log(record)
    return record


def log_failure(layer: str, partition_date: str, error: BaseException) -> None:
    append_log(
        {
            "run_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "layer": layer,
            "partition_date": partition_date,
            "error_type": type(error).__name__,
            "error": str(error),
        }
    )
