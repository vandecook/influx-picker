"""Golden tests from real data written by the core `influxdb` integration.

Each fixture in tests/fixtures/real_data_*.json holds Home Assistant states (as
read from Home Assistant) and, under `observed`, the point the core integration
really wrote to InfluxDB for that state: measurement, tags, field names, values
and types. The fixtures are produced by `tools/compare_with_influx.py --dump`,
not by the code under test.

A test fails if Influx Picker would write anything different for the same state.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from custom_components.influx_picker.schema import SchemaOptions, state_to_point

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("real_data_*.json"))


def _decode(value: Any) -> Any:
    """Restore datetime attributes (the REST API turns them into strings)."""
    if isinstance(value, dict):
        if set(value) == {"__datetime__"}:
            return datetime.fromisoformat(value["__datetime__"])
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _cases() -> list[Any]:
    cases = []
    for path in FIXTURES:
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data["states"]:
            cases.append(
                pytest.param(
                    data["options"], item, id=f"{path.stem}:{item['entity_id']}"
                )
            )
    return cases


def test_fixtures_exist() -> None:
    assert FIXTURES, "no real-data fixtures found"


@pytest.mark.parametrize(("options", "item"), _cases())
def test_matches_real_core_point(options: dict[str, Any], item: dict[str, Any]) -> None:
    observed = item["observed"]
    assert observed is not None, "fixture has no observed point"

    point = state_to_point(
        item["entity_id"],
        item["state"],
        _decode(item["attributes"]),
        datetime.fromisoformat(item["last_updated"]),
        SchemaOptions(**options),
    )
    assert point is not None

    assert point.measurement == observed["measurement"]
    assert point.tags == observed["tags"]
    assert point.fields.keys() == observed["fields"].keys()
    for key, expected in observed["fields"].items():
        actual = point.fields[key]
        # JSON keeps float vs int vs bool vs str, so the type is checked too.
        assert type(actual) is type(expected), key
        assert actual == expected, key
