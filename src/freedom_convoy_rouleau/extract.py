"""LLM extraction over the page-anchored corpus.

One request per in-scope page, via OpenRouter (z-ai/glm-5.2 by default) using
the OpenAI-compatible API with structured outputs. Citations are injected from
corpus metadata after the model returns — never model-generated. Resumable:
pages with an existing extraction file are skipped, so re-runs only touch
failures.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path

import typer
from openai import AsyncOpenAI

from .prompts import SYSTEM_PROMPT, user_prompt
from .schemas import PageExtraction
from .settings import (
    CORPUS_PATH,
    EXTRACTIONS_DIR,
    EXTRACTION_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)

app = typer.Typer(help="Run LLM extraction over the in-scope corpus pages.")

MAX_CONCURRENCY = 8
MAX_TOKENS = 16000

# $/MTok for cost reporting (z-ai/glm-5.2 on OpenRouter)
PRICE_IN, PRICE_OUT = 0.93, 3.00


PREV_CONTEXT_CHARS = 900


def load_pages(chapter: int | None) -> list[dict]:
    all_pages = [json.loads(line) for line in CORPUS_PATH.open()]
    by_key = {(p["volume"], p["printed_page"]): p for p in all_pages}
    pages = [p for p in all_pages if p["in_scope"] and p["text"].strip()]
    for p in pages:
        prev = by_key.get((p["volume"], p["printed_page"] - 1))
        # Only feed context from within the same chapter, so a chapter's first
        # page never sees out-of-scope or unrelated text.
        if prev and prev["chapter"] == p["chapter"]:
            p["prev_context"] = prev["text"][-PREV_CONTEXT_CHARS:]
        else:
            p["prev_context"] = ""
    if chapter is not None:
        pages = [p for p in pages if p["chapter"] == chapter]
    return pages


def out_path(page: dict) -> Path:
    return EXTRACTIONS_DIR / f"vol{page['volume']}_ch{page['chapter']:02d}_p{page['printed_page']:04d}.json"


def parse_tolerant(content: str) -> PageExtraction:
    """Validate model output, tolerating markdown code fences around the JSON."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return PageExtraction.model_validate_json(text)


async def extract_page(
    client: AsyncOpenAI, sem: asyncio.Semaphore, page: dict, run_id: str, usage: dict
) -> None:
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "page_extraction",
            "strict": True,
            "schema": PageExtraction.model_json_schema(),
        },
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": user_prompt(
                page["volume"],
                page["chapter"],
                page["chapter_title"],
                page["printed_page"],
                page["text"],
                page.get("prev_context", ""),
            ),
        },
    ]
    last_err: Exception | None = None
    extraction = None
    for attempt in range(3):
        async with sem:
            completion = await client.chat.completions.create(
                model=EXTRACTION_MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
                response_format=schema,
                # Route only to providers that actually honor structured outputs.
                extra_body={"provider": {"require_parameters": True}},
            )
        if completion.usage:
            usage["input"] += completion.usage.prompt_tokens
            usage["output"] += completion.usage.completion_tokens
        content = completion.choices[0].message.content or ""
        try:
            extraction = parse_tolerant(content)
            break
        except Exception as err:  # pydantic ValidationError / bad JSON — retry
            last_err = err
            typer.echo(
                f"  p{page['printed_page']} attempt {attempt + 1} invalid, retrying…", err=True
            )
    if extraction is None:
        raise RuntimeError(f"p{page['printed_page']}: {last_err}")

    record = {
        # citation fields — pipeline metadata, never model output
        "citation_volume": page["volume"],
        "citation_chapter": page["chapter"],
        "citation_printed_page": page["printed_page"],
        "citation_pdf_page": page["pdf_page_index"],
        "extraction_model": EXTRACTION_MODEL,
        "extraction_run_id": run_id,
        "extraction": extraction.model_dump(),
    }
    path = out_path(page)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1))
    n = sum(len(v) for v in extraction.model_dump().values())
    typer.echo(f"  p{page['printed_page']} ch{page['chapter']}: {n} records")


async def run_extraction(pages: list[dict], run_id: str) -> dict:
    usage = {"input": 0, "output": 0}
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async with AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY, max_retries=5
    ) as client:
        results = await asyncio.gather(
            *(extract_page(client, sem, p, run_id, usage) for p in pages),
            return_exceptions=True,
        )
    failures = [
        (p["printed_page"], r) for p, r in zip(pages, results) if isinstance(r, Exception)
    ]
    for printed_page, err in failures:
        typer.echo(f"FAILED p{printed_page}: {err}", err=True)
    if failures:
        typer.echo(f"{len(failures)} pages failed — re-run to retry just those.", err=True)
    return usage


@app.command()
def run(
    chapter: int = typer.Option(None, help="Restrict to one chapter (e.g. 10 for the pilot)"),
    yes: bool = typer.Option(False, "--yes", help="Skip the cost-confirmation gate"),
) -> None:
    """Extract facts from all (or one chapter's) in-scope pages."""
    if not OPENROUTER_API_KEY:
        typer.echo("OPENROUTER_API_KEY is not set (add it to .env).", err=True)
        raise typer.Exit(code=1)

    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    pages = load_pages(chapter)
    todo = [p for p in pages if not out_path(p).exists()]
    typer.echo(f"{len(pages)} in-scope pages; {len(todo)} not yet extracted.")
    if not todo:
        typer.echo("Nothing to do.")
        raise typer.Exit()

    # Cost gate: rough estimate from corpus size (chars/4 ≈ tokens).
    est_in = sum(len(p["text"]) // 4 + len(SYSTEM_PROMPT) // 4 for p in todo)
    est_out = len(todo) * 2500
    est_cost = est_in / 1e6 * PRICE_IN + est_out / 1e6 * PRICE_OUT
    typer.echo(
        f"Model {EXTRACTION_MODEL}; estimated ≤ ${est_cost:.2f} "
        f"(~{est_in/1000:.0f}K in / ~{est_out/1000:.0f}K out)"
    )
    if not yes:
        typer.confirm("Proceed with billed extraction?", abort=True)

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    usage = asyncio.run(run_extraction(todo, run_id))

    cost = usage["input"] / 1e6 * PRICE_IN + usage["output"] / 1e6 * PRICE_OUT
    typer.echo(
        f"Done. run_id={run_id} tokens: {usage['input']:,} in / {usage['output']:,} out "
        f"→ actual cost ≈ ${cost:.2f}"
    )


if __name__ == "__main__":
    app()
