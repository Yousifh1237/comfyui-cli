"""Output formatting utilities for CLI and JSON output."""

import json
import sys
from typing import Any


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as JSON string."""
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def format_table(rows: list[dict], columns: list[str] | None = None,
                 max_width: int = 80) -> str:
    """Format a list of dicts as a text table."""
    if not rows:
        return "(no data)"

    if columns is None:
        columns = list(rows[0].keys())

    # Calculate column widths
    widths: dict[str, int] = {}
    for col in columns:
        widths[col] = len(str(col))
        for row in rows:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    # Truncate if needed
    total = sum(widths.values()) + (len(columns) - 1) * 3
    if total > max_width and len(columns) > 1:
        excess = total - max_width
        # Shrink the widest column
        widest = max(columns, key=lambda c: widths[c])
        widths[widest] = max(10, widths[widest] - excess)

    # Build header
    header_parts = []
    sep_parts = []
    for col in columns:
        w = widths[col]
        header_parts.append(str(col).ljust(w)[:w])
        sep_parts.append("-" * w)

    lines = [" | ".join(header_parts), "-+-".join(sep_parts)]

    # Build rows
    for row in rows:
        parts = []
        for col in columns:
            val = str(row.get(col, ""))
            w = widths[col]
            if len(val) > w:
                val = val[:w - 1] + "~"
            parts.append(val.ljust(w))
        lines.append(" | ".join(parts))

    return "\n".join(lines)


def format_list(items: list, prefix: str = "  - ") -> str:
    """Format a list with bullet points."""
    if not items:
        return "(none)"
    return "\n".join(f"{prefix}{item}" for item in items)


def format_kv(data: dict, indent: int = 0) -> str:
    """Format key-value pairs."""
    if not data:
        return "(empty)"
    prefix = " " * indent
    max_key = max(len(str(k)) for k in data)
    lines = []
    for key, value in data.items():
        lines.append(f"{prefix}{str(key).ljust(max_key)} : {value}")
    return "\n".join(lines)


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


class OutputFormatter:
    """Manages output formatting based on --json flag."""

    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode

    def output(self, data: Any, human_text: str | None = None) -> str:
        """Output data in the appropriate format."""
        if self.json_mode:
            result = format_json(data)
        else:
            result = human_text if human_text is not None else format_json(data)
        return result

    def print(self, data: Any, human_text: str | None = None) -> None:
        """Print data to stdout."""
        print(self.output(data, human_text))

    def error(self, message: str, data: dict | None = None) -> None:
        """Print error message."""
        if self.json_mode:
            err = {"error": message}
            if data:
                err["details"] = data
            print(format_json(err), file=sys.stderr)
        else:
            print(f"Error: {message}", file=sys.stderr)
            if data:
                for k, v in data.items():
                    print(f"  {k}: {v}", file=sys.stderr)
