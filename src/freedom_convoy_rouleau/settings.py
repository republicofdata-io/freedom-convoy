"""Paths and environment for the Rouleau pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]

CHAPTER_MAP_PATH = REPO_ROOT / "config" / "rouleau_chapters.yaml"
CHECKSUMS_PATH = REPO_ROOT / "config" / "rouleau_checksums.sha256"
ALIASES_PATH = REPO_ROOT / "config" / "rouleau_aliases.yaml"

RAW_PDF_DIR = REPO_ROOT / "data" / "raw" / "rouleau"
CORPUS_PATH = REPO_ROOT / "data" / "processed" / "rouleau" / "corpus.jsonl"
EXTRACTIONS_DIR = REPO_ROOT / "data" / "processed" / "rouleau" / "extractions"
TABLES_DIR = REPO_ROOT / "data" / "parquet" / "rouleau"
QA_DIR = REPO_ROOT / "data" / "processed" / "rouleau" / "qa"
DUCKDB_PATH = REPO_ROOT / "data" / "freedom_convoy.duckdb"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EXTRACTION_MODEL = os.getenv("ROULEAU_EXTRACTION_MODEL", "z-ai/glm-5.2")
