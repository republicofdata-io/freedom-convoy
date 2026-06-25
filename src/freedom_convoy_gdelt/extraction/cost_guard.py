"""BigQuery dry-run estimates and billed-query scan ceiling."""

from __future__ import annotations

from dataclasses import dataclass

from google.cloud import bigquery

from .settings import billing_project, max_scan_gib

USD_PER_TIB = 6.25
BYTES_PER_TIB = 1024**4
BYTES_PER_GIB = 1024**3


class ScanCeilingExceeded(RuntimeError):
    """Raised when a query's dry-run estimate exceeds the configured ceiling."""


@dataclass(frozen=True)
class CostEstimate:
    bytes_processed: int
    gib: float
    usd: float

    @property
    def human(self) -> str:
        return f"{self.gib:.3f} GiB (~${self.usd:.4f})"


def bigquery_client() -> bigquery.Client:
    return bigquery.Client(project=billing_project())


def estimate_from_bytes(total_bytes: int) -> CostEstimate:
    return CostEstimate(
        bytes_processed=total_bytes,
        gib=total_bytes / BYTES_PER_GIB,
        usd=total_bytes / BYTES_PER_TIB * USD_PER_TIB,
    )


def estimate_bytes(client: bigquery.Client, sql: str) -> CostEstimate:
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    return estimate_from_bytes(job.total_bytes_processed or 0)


def guarded_query(
    client: bigquery.Client,
    sql: str,
    *,
    override_ceiling: bool = False,
):
    estimate = estimate_bytes(client, sql)
    ceiling = max_scan_gib()
    if not override_ceiling and estimate.gib > ceiling:
        raise ScanCeilingExceeded(
            f"Query would scan {estimate.human}, over BQ_MAX_SCAN_GIB={ceiling:.1f}. "
            "Raise the ceiling only after reviewing `make cost-*` output."
        )
    return client.query(sql).result(), estimate
