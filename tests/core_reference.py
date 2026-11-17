"""Reference copy of the core integration's state-to-point conversion.

Copied from Home Assistant Core, `homeassistant/components/influxdb/__init__.py`
(`_generate_event_to_json`, branch `dev`, 2026-11-17), licensed under the
Apache License 2.0, Copyright Home Assistant contributors. Only the include /
exclude filter and the config parsing were removed. Used by tests only, to
compare Influx Picker's output with the original algorithm.

When the core integration changes, update this copy and run the tests.
"""

from __future__ import annotations

from contextlib import suppress
import math
import re
from typing import Any

from homeassistant.core import State
from homeassistant.helpers import state as state_helper
from homeassistant.helpers.entity_values import EntityValues

RE_DIGIT_TAIL = re.compile(r"^[^\.]*\d+\.?\d+[^\.]*$")
RE_DECIMAL = re.compile(r"[^\d.]+")


def _single_line(value: str) -> str:
    return " ".join(value.splitlines())


def core_event_to_json(
    state: State,
    time_fired: Any,
    *,
    tags: dict[str, str] | None = None,
    tags_attributes: list[str] | None = None,
    default_measurement: str | None = None,
    measurement_attr: str = "unit_of_measurement",
    override_measurement: str | None = None,
    ignore_attributes: list[str] | None = None,
    component_config: dict | None = None,
    component_config_domain: dict | None = None,
    component_config_glob: dict | None = None,
) -> dict[str, Any] | None:
    """Return the dict the core integration would pass to the client."""
    tags = {key: _single_line(value) for key, value in (tags or {}).items()}
    tags_attributes = tags_attributes or []
    global_ignore_attributes = set(ignore_attributes or [])
    entity_values = EntityValues(
        component_config or {},
        component_config_domain or {},
        component_config_glob or {},
    )

    if state is None or state.state in ("unknown", "", "unavailable", None):
        return None

    try:
        _include_state = _include_value = False

        _state_as_value = float(state.state)
        _include_value = True
    except ValueError:
        try:
            _state_as_value = float(state_helper.state_as_number(state))
            _include_state = _include_value = True
        except ValueError:
            _include_state = True

    include_uom = True
    include_dc = True
    entity_config = entity_values.get(state.entity_id)
    measurement = entity_config.get("override_measurement")
    if measurement in (None, ""):
        if override_measurement:
            measurement = override_measurement
        else:
            if measurement_attr == "entity_id":
                measurement = state.entity_id
            elif measurement_attr == "domain__device_class":
                device_class = state.attributes.get("device_class")
                if device_class is None:
                    measurement = state.domain
                else:
                    measurement = f"{state.domain}__{device_class}"
                    include_dc = False
            else:
                measurement = state.attributes.get(measurement_attr)
            if measurement in (None, ""):
                if default_measurement:
                    measurement = default_measurement
                else:
                    measurement = state.entity_id
            else:
                include_uom = measurement_attr != "unit_of_measurement"

    if isinstance(measurement, str):
        measurement = _single_line(measurement)

    json: dict[str, Any] = {
        "measurement": measurement,
        "tags": {"domain": state.domain, "entity_id": state.object_id},
        "time": time_fired,
        "fields": {},
    }
    if _include_state:
        json["fields"]["state"] = _single_line(state.state)
    if _include_value:
        json["fields"]["value"] = _state_as_value

    ignore = set(entity_config.get("ignore_attributes", []))
    ignore.update(global_ignore_attributes)
    for key, value in state.attributes.items():
        if key in tags_attributes:
            json["tags"][key] = _single_line(value) if isinstance(value, str) else value
        elif (
            (key != "unit_of_measurement" or include_uom)
            and (key != "device_class" or include_dc)
            and key not in ignore
        ):
            if key in json["fields"]:
                key = f"{key}_"
            try:
                json["fields"][key] = float(value)
            except (ValueError, TypeError):
                new_key = f"{key}_str"
                new_value = _single_line(str(value))
                json["fields"][new_key] = new_value

                if RE_DIGIT_TAIL.match(new_value):
                    json["fields"][key] = float(RE_DECIMAL.sub("", new_value))

            with suppress(KeyError, TypeError):
                if not math.isfinite(json["fields"][key]):
                    del json["fields"][key]

    fields = json["fields"]
    if "time" in fields:
        key = "time_"
        while key in fields:
            key = f"{key}_"
        fields[key] = fields.pop("time")

    json["tags"].update(tags)
    return json
