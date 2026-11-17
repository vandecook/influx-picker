"""Neutral point model, independent of the InfluxDB version.

This module must not import Home Assistant, so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

FieldValue = float | int | bool | str


@dataclass(slots=True)
class Point:
    """One data point: measurement, tags, fields and a timestamp."""

    measurement: str
    time: datetime
    tags: dict[str, str] = field(default_factory=dict)
    fields: dict[str, FieldValue] = field(default_factory=dict)
