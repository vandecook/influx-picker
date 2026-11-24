"""Unit tests for the line protocol serializer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.series_picker.line_protocol import timestamp, to_body, to_line
from custom_components.series_picker.point import Point

T = datetime(2026, 11, 17, 12, 0, 0, 123456, tzinfo=UTC)
TS = 1794916800123456000


def _p(**kwargs) -> Point:
    kwargs.setdefault("measurement", "m")
    kwargs.setdefault("time", T)
    kwargs.setdefault("fields", {"v": 1.0})
    return Point(**kwargs)


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (1.0, "1"),
        (1.5, "1.5"),
        (-0.0, "-0"),
        (1e20, "1e+20"),
        (1e-7, "1e-07"),
        (3, "3i"),
        (True, "true"),
        (False, "false"),
        ("a", '"a"'),
        ('q"b\\', '"q\\"b\\\\"'),
    ],
)
def test_field_values(value, text) -> None:
    """Field values use the client's formatting."""
    assert to_line(_p(fields={"f": value})) == f"m f={text} {TS}"


def test_non_finite_fields_are_skipped() -> None:
    """NaN and infinity are dropped; a point with no field left is empty."""
    assert to_line(_p(fields={"a": float("nan"), "b": 1.0})) == f"m b=1 {TS}"
    assert to_line(_p(fields={"a": float("inf")})) == ""
    assert to_line(_p(fields={})) == ""


def test_unsupported_field_type() -> None:
    """Other types are a programming error."""
    with pytest.raises(ValueError):
        to_line(_p(fields={"a": [1]}))


def test_escaping() -> None:
    """Measurement, tag and field key escaping."""
    point = _p(
        measurement="a b,c=d",
        tags={"t k": "v,1=2", "path": "c:\\", "empty": ""},
        fields={"f=x y": 1.0},
    )
    assert to_line(point) == (
        f"a\\ b\\,c=d,path=c:\\ ,t\\ k=v\\,1\\=2 f\\=x\\ y=1 {TS}"
    )


def test_tags_and_fields_sorted() -> None:
    """Keys are sorted like the official client does."""
    point = _p(tags={"b": "2", "a": "1"}, fields={"z": 1.0, "y": 2.0})
    assert to_line(point) == f"m,a=1,b=2 y=2,z=1 {TS}"


def test_naive_datetime_is_utc() -> None:
    """A naive datetime is treated as UTC."""
    assert timestamp(T.replace(tzinfo=None)) == TS


def test_body_skips_empty_points() -> None:
    """Empty lines are left out of the request body."""
    body = to_body([_p(), _p(fields={}), _p(fields={"v": 2.0})])
    assert body == f"m v=1 {TS}\nm v=2 {TS}"
