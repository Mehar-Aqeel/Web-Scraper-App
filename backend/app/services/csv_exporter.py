import html
import io
from typing import Any

import pandas as pd

# Characters that trigger formula injection in spreadsheet apps
_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _sanitise(value: Any) -> Any:
    """Neutralise formula injection and HTML in string cell values.

    - Prefixes formula-injection characters (=, +, -, @) with a single quote.
    - HTML-escapes angle brackets so scraped <script> tags can't execute if
      the CSV is ever rendered in a browser-based viewer.
    """
    if not isinstance(value, str):
        return value
    if value.startswith(_INJECTION_PREFIXES):
        value = f"'{value}"
    return html.escape(value, quote=False)


def generate_csv(rows: list[dict]) -> bytes:
    """Return UTF-8 encoded CSV bytes from *rows* with formula-injection protection."""
    if not rows:
        df = pd.DataFrame(columns=["type", "value", "text", "level", "source_url"])
    else:
        df = pd.DataFrame(rows)

    # Sanitise every string cell
    df = df.map(_sanitise)  # type: ignore[attr-defined]

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
