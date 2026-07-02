"""Page-anchored corpus builder.

Emits one JSONL record per report page:
    {volume, pdf_page_index, printed_page, chapter, chapter_title, in_scope, text}

The printed page number is parsed from the "- N -" footer and cross-checked
against the chapter map's printed==pdf-index invariant for Volumes 2-3. Any
page where the footer disagrees is a hard error — the citation backbone must
be deterministic before anything else runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz
import typer
import yaml

from .settings import CHAPTER_MAP_PATH, CORPUS_PATH, REPO_ROOT

app = typer.Typer(help="Build the page-anchored text corpus from the report PDFs.")

FOOTER_RE = re.compile(r"^-\s*(\d+)\s*-$")
HEADER_MAX_Y = 60  # running heads sit at y0≈44
FOOTER_MIN_Y = 730  # page-number footer sits at y0≈745


@dataclass
class PageRecord:
    volume: int
    pdf_page_index: int  # 0-based
    printed_page: int
    chapter: int
    chapter_title: str
    in_scope: bool
    text: str


def load_chapter_map() -> dict:
    return yaml.safe_load(CHAPTER_MAP_PATH.read_text())


def chapter_for_page(printed_page: int, chapters: list[dict]) -> dict | None:
    for ch in chapters:
        if ch["printed_start"] <= printed_page <= ch["printed_end"]:
            return ch
    return None


def extract_page(page: fitz.Page) -> tuple[str, int | None]:
    """Return (body_text, printed_page_from_footer) with header/footer stripped."""
    blocks = page.get_text("blocks", sort=True)
    body: list[str] = []
    printed: int | None = None
    for x0, y0, x1, y1, text, *_ in blocks:
        stripped = text.strip()
        if y0 < HEADER_MAX_Y:
            continue
        if y0 > FOOTER_MIN_Y:
            m = FOOTER_RE.match(stripped)
            if m:
                printed = int(m.group(1))
            continue
        if stripped:
            body.append(stripped)
    return "\n".join(body), printed


@app.command()
def build(out: str = str(CORPUS_PATH)) -> None:
    """Extract every chapter-mapped page of Vols 2-3 into a JSONL corpus."""
    chapter_map = load_chapter_map()
    out_path = Path(out) if out.startswith("/") else REPO_ROOT / out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[PageRecord] = []
    footer_mismatches: list[str] = []

    for vol in chapter_map["volumes"]:
        doc = fitz.open(REPO_ROOT / vol["pdf"])
        chapters = vol["chapters"]
        lo = min(c["printed_start"] for c in chapters)
        hi = max(c["printed_end"] for c in chapters)
        for pdf_idx in range(lo, hi + 1):  # printed == 0-based pdf index (validated below)
            text, footer_printed = extract_page(doc[pdf_idx])
            if footer_printed is not None and footer_printed != pdf_idx:
                footer_mismatches.append(
                    f"Vol {vol['volume']} pdf_idx {pdf_idx}: footer says {footer_printed}"
                )
                continue
            printed = footer_printed if footer_printed is not None else pdf_idx
            ch = chapter_for_page(printed, chapters)
            if ch is None:
                continue
            records.append(
                PageRecord(
                    volume=vol["volume"],
                    pdf_page_index=pdf_idx,
                    printed_page=printed,
                    chapter=ch["chapter"],
                    chapter_title=ch["title"],
                    in_scope=ch["in_scope"],
                    text=text,
                )
            )
        doc.close()

    if footer_mismatches:
        for m in footer_mismatches:
            typer.echo(f"FOOTER MISMATCH: {m}", err=True)
        raise typer.Exit(code=1)

    with out_path.open("w") as f:
        for rec in records:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")

    in_scope = sum(1 for r in records if r.in_scope)
    empty = sum(1 for r in records if not r.text)
    typer.echo(
        f"Wrote {len(records)} pages ({in_scope} in scope, "
        f"{len(records) - in_scope} out of scope) to {out_path}"
    )
    if empty:
        typer.echo(f"NOTE: {empty} pages had empty body text", err=True)


if __name__ == "__main__":
    app()
