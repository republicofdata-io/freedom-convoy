"""Window/date helpers for extraction CLIs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

from .settings import window_end, window_start


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def days(start: date, end: date) -> Iterator[date]:
    cursor = start
    while cursor <= end:
        yield cursor
        cursor += timedelta(days=1)


def configured_window() -> tuple[date, date]:
    return parse_day(window_start()), parse_day(window_end())


def validate_range(start: date, end: date) -> tuple[date, date]:
    """Validate an extraction range against the configured corpus window."""
    win_start, win_end = configured_window()
    if start > end:
        raise ValueError(f"Range start {start.isoformat()} is after end {end.isoformat()}")
    if start < win_start or end > win_end:
        raise ValueError(
            f"Range {start.isoformat()} -> {end.isoformat()} is outside the configured "
            f"window {win_start.isoformat()} -> {win_end.isoformat()}"
        )
    return start, end


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + (mon == 12), (mon % 12) + 1, 1) - timedelta(days=1)
    win_start, win_end = configured_window()
    clipped_start, clipped_end = max(start, win_start), min(end, win_end)
    return validate_range(clipped_start, clipped_end)
