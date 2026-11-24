"""Compare Series Picker with the core algorithm and the official client.

For every case, the core reference conversion (tests/core_reference.py) is
serialized with the official `influxdb-client` package, exactly as the core
integration does for InfluxDB 2. Series Picker must produce the same line.
"""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.core import State
from homeassistant.helpers import state as state_helper
from influxdb_client import Point as ClientPoint
import pytest

from custom_components.series_picker import schema
from custom_components.series_picker.line_protocol import to_line
from custom_components.series_picker.schema import (
    EntityCustomization,
    SchemaOptions,
    state_to_point,
)

from .core_reference import core_event_to_json

T = datetime(2026, 11, 17, 12, 0, 0, 123456, tzinfo=UTC)

ATTRS_ZOO = {
    "unit_of_measurement": "W",
    "device_class": "power",
    "friendly_name": 'Zoo, "quoted" = x\\y',
    "value": 1,
    "state": "on",
    "int": 7,
    "float": 1.25,
    "big": 1e20,
    "small": 1e-7,
    "neg": -3,
    "bool_t": True,
    "bool_f": False,
    "none": None,
    "list": [1, 2],
    "dict": {"a": 1},
    "inf": float("inf"),
    "str_inf": "inf",
    "digits": "abc 123 def",
    "two_dots": "1.2.3",
    "unicode": "Grüße ☃",
    "newline": "line1\nline2\r\nline3",
    "tab": "a\tb",
    "time": 3,
    "time_": "x",
    "key with space": 1,
    "key,comma": "v",
    "key=eq": 2,
}

STATES = [
    ("sensor.a", "21.5", {"unit_of_measurement": "°C"}),
    ("sensor.b", "0", {}),
    ("sensor.c", "-0.0", {}),
    ("sensor.d", "1e3", {}),
    ("sensor.e", "nan", {}),
    ("sensor.f", "inf", {}),
    ("binary_sensor.g", "on", {"device_class": "motion"}),
    ("lock.h", "locked", {}),
    ("lock.i", "unlocked", {}),
    ("cover.j", "open", {}),
    ("cover.k", "closed", {}),
    ("device_tracker.l", "home", {}),
    ("device_tracker.m", "not_home", {}),
    ("sun.sun", "above_horizon", {"elevation": 12.3}),
    ("sun.sun", "below_horizon", {}),
    ("climate.n", "heat", {"temperature": 21}),
    ("sensor.o", "multi\nline", {}),
    ("sensor.p", "12", ATTRS_ZOO),
    ("sensor.q", "text", ATTRS_ZOO),
    ("sensor.r", "5", {"unit_of_measurement": "", "device_class": "x"}),
    ("sensor.s", "5", {"unit_of_measurement": "a b,c=d\ne"}),
    ("sensor.t", "5", {"unit_of_measurement": 5}),
    (
        "sensor.u",
        "5",
        {"room": "Living Room", "floor": 2, "nothing": None, "empty": ""},
    ),
    ("input_text.v", 'say "hi" \\ bye', {}),
    ("sensor.w", "unknown", {}),
]

OPTION_SETS = [
    {},
    {"measurement_attr": "domain__device_class"},
    {"measurement_attr": "entity_id"},
    {"override_measurement": "ha"},
    {"default_measurement": "units"},
    {"tags": {"instance": "main", "domain": "override"}},
    {"tags_attributes": ["room", "floor", "nothing", "empty", "friendly_name"]},
    {"ignore_attributes": ["friendly_name", "value"]},
    {
        "component_config": {"sensor.p": {"override_measurement": "p_custom"}},
        "component_config_domain": {"sensor": {"ignore_attributes": ["int"]}},
        "component_config_glob": {"sensor.[pq]": {"override_measurement": "glob"}},
    },
]


def _to_schema_options(opts: dict) -> SchemaOptions:
    def custom(mapping: dict) -> dict[str, EntityCustomization]:
        return {
            key: EntityCustomization(
                override_measurement=value.get("override_measurement"),
                ignore_attributes=value.get("ignore_attributes"),
            )
            for key, value in mapping.items()
        }

    return SchemaOptions(
        measurement_attr=opts.get("measurement_attr", "unit_of_measurement"),
        default_measurement=opts.get("default_measurement"),
        override_measurement=opts.get("override_measurement"),
        tags=opts.get("tags", {}),
        tags_attributes=opts.get("tags_attributes", []),
        ignore_attributes=opts.get("ignore_attributes", []),
        component_config=custom(opts.get("component_config", {})),
        component_config_domain=custom(opts.get("component_config_domain", {})),
        component_config_glob=custom(opts.get("component_config_glob", {})),
    )


@pytest.mark.parametrize("opts", OPTION_SETS, ids=lambda o: ",".join(o) or "defaults")
@pytest.mark.parametrize(
    ("entity_id", "state", "attributes"),
    STATES,
    ids=[f"{e}={s!r}" for e, s, _ in STATES],
)
def test_matches_core(entity_id, state, attributes, opts) -> None:
    """Same line as core conversion + official client."""
    ha_state = State(entity_id, state, attributes)
    reference = core_event_to_json(ha_state, T, **opts)
    ours = state_to_point(entity_id, state, attributes, T, _to_schema_options(opts))
    if reference is None:
        assert ours is None
        return
    assert ours is not None
    expected = ClientPoint.from_dict(reference).to_line_protocol()
    assert to_line(ours) == expected


@pytest.mark.parametrize(
    "state",
    [
        "on",
        "off",
        "locked",
        "unlocked",
        "open",
        "closed",
        "home",
        "not_home",
        "above_horizon",
        "below_horizon",
        "unknown",
        "heat",
        "1.5",
        "",
    ],
)
def test_state_as_number_table_matches_home_assistant(state) -> None:
    """Our copy of the on/off table matches Home Assistant's helper."""
    try:
        expected = float(state_helper.state_as_number(State("sensor.x", state or "x")))
    except ValueError:
        expected = None
    try:
        ours = schema.state_as_number(state or "x")
    except ValueError:
        ours = None
    assert ours == expected
