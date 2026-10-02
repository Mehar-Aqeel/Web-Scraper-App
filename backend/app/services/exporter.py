"""JSON and Excel export (TICKET-026)."""
from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from app.services.csv_exporter import _sanitise


def generate_json(rows: list[dict[str, Any]]) -> bytes:
    """Return UTF-8 encoded JSON bytes."""
    return json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")


def generate_excel(rows: list[dict[str, Any]]) -> bytes:
    """Return Excel (.xlsx) bytes with formula-injection protection."""
    if not rows:
        df = pd.DataFrame(columns=["type", "value", "text", "level", "source_url"])
    else:
        df = pd.DataFrame(rows)

    df = df.map(_sanitise)  # type: ignore[attr-defined]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Extraction")
    return buf.getvalue()
