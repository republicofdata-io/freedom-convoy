"""Render GDELT SQL templates from the configured convoy boundary."""

from __future__ import annotations

from .settings import (
    PARTITION_TOKEN,
    QUERY_NAMES,
    REGEX_TOKEN,
    SOURCE_COLLECTION_TOKEN,
    SQL_DIR,
    candidate_config,
    source_collection_id,
)


def convoy_regex() -> str:
    patterns = candidate_config().get("convoy_patterns", [])
    if not patterns:
        raise ValueError("convoy_patterns is empty in config/gdelt_candidate.yaml")
    return "(" + "|".join(patterns) + ")"


def render_query(name: str, partition_date: str) -> str:
    if name not in QUERY_NAMES:
        raise ValueError(f"Unknown query {name!r}; expected one of {QUERY_NAMES}")
    path = SQL_DIR / f"{name}.sql"
    if not path.is_file():
        raise FileNotFoundError(f"SQL template not found: {path}")
    return (
        path.read_text()
        .replace(REGEX_TOKEN, convoy_regex())
        .replace(PARTITION_TOKEN, partition_date)
        .replace(SOURCE_COLLECTION_TOKEN, str(source_collection_id()))
    )
