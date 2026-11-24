"""Line protocol serializer shared by all backends.

The output matches the official InfluxDB Python client, which the core
integration uses (see docs/core-schema-audit.md, section 6). This module must
not import Home Assistant.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import math

from .point import Point

_ESCAPE_MEASUREMENT = str.maketrans(
    {",": r"\,", " ": r"\ ", "\n": r"\n", "\t": r"\t", "\r": r"\r"}
)
_ESCAPE_KEY = str.maketrans(
    {",": r"\,", "=": r"\=", " ": r"\ ", "\n": r"\n", "\t": r"\t", "\r": r"\r"}
)
_ESCAPE_STRING = str.maketrans({'"': r"\"", "\\": r"\\"})

PRECISIONS = ("s", "ms", "us", "ns")
_NS_PER_UNIT = {"ns": 1, "us": 1_000, "ms": 1_000_000, "s": 1_000_000_000}
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _escape_tag_value(value: str) -> str:
    escaped = value.translate(_ESCAPE_KEY)
    if escaped.endswith("\\"):
        escaped += " "
    return escaped


def _format_field(value: object) -> str | None:
    """Return the line protocol form of a field value, or None to skip it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        text = str(value)
        return text[:-2] if text.endswith(".0") else text
    if isinstance(value, int):
        return f"{value}i"
    if isinstance(value, str):
        return f'"{value.translate(_ESCAPE_STRING)}"'
    raise ValueError(f"Unsupported field type: {type(value).__name__}")


def timestamp(time: datetime, precision: str = "ns") -> int:
    """Convert a datetime to an integer timestamp in the given precision.

    Naive datetimes are treated as UTC. Sub-unit parts are truncated.
    """
    if time.tzinfo is None:
        time = time.replace(tzinfo=UTC)
    delta = time - _EPOCH
    ns = (delta.days * 86_400 + delta.seconds) * 1_000_000_000
    ns += delta.microseconds * 1_000
    return ns // _NS_PER_UNIT[precision]


def to_line(point: Point, precision: str = "ns") -> str:
    """Serialize one point. Returns "" if the point has no writable field."""
    fields = []
    for key, value in sorted(point.fields.items()):
        if value is None:
            continue
        formatted = _format_field(value)
        if formatted is not None:
            fields.append(f"{key.translate(_ESCAPE_KEY)}={formatted}")
    if not fields:
        return ""

    tags = []
    for key, value in sorted(point.tags.items()):
        if value is None:
            continue
        tag_key = str(key).translate(_ESCAPE_KEY)
        tag_value = _escape_tag_value(str(value))
        if tag_key and tag_value:
            tags.append(f"{tag_key}={tag_value}")

    measurement = str(point.measurement).translate(_ESCAPE_MEASUREMENT)
    tag_part = "," + ",".join(tags) if tags else ""
    return (
        f"{measurement}{tag_part} {','.join(fields)} {timestamp(point.time, precision)}"
    )


def to_body(points: Iterable[Point], precision: str = "ns") -> str:
    """Serialize many points into a request body, skipping empty lines."""
    return "\n".join(line for p in points if (line := to_line(p, precision)))
