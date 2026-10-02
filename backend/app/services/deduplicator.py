"""Server-side duplicate detection (TICKET-029a).

Removes duplicate records from the full result set before pagination,
keyed on (type, value) — distinct from the client-side dedup filter.
"""
from __future__ import annotations


def deduplicate(records: list[dict]) -> list[dict]:
    """Return *records* with exact (type, value) duplicates removed, preserving order."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in records:
        key = (row.get("type"), row.get("value"))
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out
