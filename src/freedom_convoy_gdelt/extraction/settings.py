"""Shared extraction settings and config loading."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = REPO_ROOT / "sql"
CONFIG_PATH = REPO_ROOT / "config" / "gdelt_candidate.yaml"

QUERY_NAMES = (
    "gdelt_candidate_gkg",
    "gdelt_events_candidate",
    "gdelt_mentions_for_events",
)
LAYERS = {
    "gdelt_gkg": "gdelt_candidate_gkg",
    "gdelt_events": "gdelt_events_candidate",
    "gdelt_mentions": "gdelt_mentions_for_events",
}

PARTITION_TOKEN = "__PARTITION_DATE__"
REGEX_TOKEN = "__CONVOY_REGEX__"
SOURCE_COLLECTION_TOKEN = "__SOURCE_COLLECTION_ID__"

load_dotenv(REPO_ROOT / ".env")


@cache
def candidate_config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text())


def window_start() -> str:
    return str(candidate_config()["window"]["start"])


def window_end() -> str:
    return str(candidate_config()["window"]["end"])


def source_collection_id() -> int:
    return int(candidate_config().get("gkg", {}).get("source_collection_id", 1))


def data_dir() -> Path:
    return (REPO_ROOT / os.getenv("DATA_DIR", "./data/parquet")).resolve()


def log_dir() -> Path:
    return (REPO_ROOT / os.getenv("EXTRACTION_LOG_DIR", "./data/logs")).resolve()


def billing_project() -> str:
    project = os.getenv("BIGQUERY_PROJECT_ID", "").strip()
    if not project:
        raise RuntimeError(
            "BIGQUERY_PROJECT_ID is not set. Copy .env.example to .env or export it."
        )
    return project


def max_scan_gib() -> float:
    raw = os.getenv("BQ_MAX_SCAN_GIB", "20").strip()
    try:
        return float(raw)
    except ValueError:
        return 20.0
