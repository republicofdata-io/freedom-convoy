"""Citation-fidelity verification.

For every extracted record, confirm its source_quote actually appears on the
cited page: exact substring after whitespace/quote normalization, or fuzzy
(≥95% similarity) to tolerate ligature and hyphenation artifacts. Failures are
quarantined, never silently dropped. Also scans quotes for conclusion markers
(the third control layer against Commissioner-opinion leakage).
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata

import typer

from .settings import CORPUS_PATH, EXTRACTIONS_DIR, QA_DIR

app = typer.Typer(help="Verify every record's source_quote against the cited page text.")

CONCLUSION_MARKERS = [
    "i find",
    "i conclude",
    "in my view",
    "i am satisfied",
    "i accept that",
    "i recommend",
    "the commissioner concludes",
    "it is my opinion",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"-\s*\n\s*", "", text)  # rejoin hyphenated line breaks
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def quote_matches(quote: str, page_text: str) -> tuple[bool, float]:
    q, p = normalize(quote), normalize(page_text)
    if q in p:
        return True, 1.0
    # Fuzzy: best-window similarity for quotes mangled by extraction artifacts.
    matcher = difflib.SequenceMatcher(None, q, p, autojunk=False)
    blocks = matcher.get_matching_blocks()
    matched = sum(b.size for b in blocks)
    ratio = matched / max(len(q), 1)
    return ratio >= 0.95, ratio


@app.command()
def run() -> None:
    pages = {
        (p["volume"], p["printed_page"]): p["text"]
        for p in (json.loads(line) for line in CORPUS_PATH.open())
    }
    QA_DIR.mkdir(parents=True, exist_ok=True)

    total = passed = 0
    quarantined: list[dict] = []
    conclusion_flags: list[dict] = []

    for path in sorted(EXTRACTIONS_DIR.glob("*.json")):
        rec = json.loads(path.read_text())
        page_text = pages[(rec["citation_volume"], rec["citation_printed_page"])]
        for table, rows in rec["extraction"].items():
            for i, row in enumerate(rows):
                total += 1
                ok, ratio = quote_matches(row["source_quote"], page_text)
                meta = {
                    "file": path.name,
                    "table": table,
                    "index": i,
                    "printed_page": rec["citation_printed_page"],
                    "match_ratio": round(ratio, 3),
                    "record": row,
                }
                if ok:
                    passed += 1
                else:
                    quarantined.append(meta)
                if any(m in row["source_quote"].lower() for m in CONCLUSION_MARKERS):
                    conclusion_flags.append(meta)

    (QA_DIR / "quarantine.json").write_text(json.dumps(quarantined, ensure_ascii=False, indent=1))
    (QA_DIR / "conclusion_flags.json").write_text(
        json.dumps(conclusion_flags, ensure_ascii=False, indent=1)
    )

    pct = 100 * passed / total if total else 0.0
    typer.echo(f"{passed}/{total} records citation-verified ({pct:.2f}%)")
    typer.echo(f"{len(quarantined)} quarantined → {QA_DIR / 'quarantine.json'}")
    typer.echo(f"{len(conclusion_flags)} conclusion-marker flags → {QA_DIR / 'conclusion_flags.json'}")
    if pct < 95:
        typer.echo("BELOW 95% THRESHOLD — revise prompt and re-run affected pages.", err=True)
        raise typer.Exit(code=1)


@app.command()
def sample(n: int = typer.Option(45, help="Total records in the stratified sample")) -> None:
    """Draw a chapter-stratified sample of records for human spot-checking."""
    import csv
    import random

    rng = random.Random(17)  # deterministic; seeded with the ticket number
    by_chapter: dict[int, list[dict]] = {}
    for path in sorted(EXTRACTIONS_DIR.glob("*.json")):
        rec = json.loads(path.read_text())
        for table, rows in rec["extraction"].items():
            for row in rows:
                by_chapter.setdefault(rec["citation_chapter"], []).append({
                    "chapter": rec["citation_chapter"],
                    "printed_page": rec["citation_printed_page"],
                    "table": table,
                    "name_or_title": row.get("name") or row.get("title", ""),
                    "source_quote": row["source_quote"],
                    "verified_by_human": "",
                })
    per_chapter = max(1, n // max(len(by_chapter), 1))
    picked = []
    for chapter, rows in sorted(by_chapter.items()):
        picked += rng.sample(rows, min(per_chapter, len(rows)))

    QA_DIR.mkdir(parents=True, exist_ok=True)
    out = QA_DIR / "human_sample.csv"
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(picked[0].keys()))
        writer.writeheader()
        writer.writerows(picked)
    typer.echo(f"{len(picked)} records ({per_chapter}/chapter) → {out}")


if __name__ == "__main__":
    app()
