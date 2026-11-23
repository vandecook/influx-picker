"""Convert a Home Assistant state into a Point, compatible with the core integration.

Every rule here mirrors `_generate_event_to_json` of the core `influxdb`
integration. See docs/core-schema-audit.md for the rules and their sources.
This module must not import Home Assistant: it works on plain values so the
golden tests run without a Home Assistant instance.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
import fnmatch
import math
import re
from typing import Any

from .point import FieldValue, Point

MEASUREMENT_ATTR_UNIT = "unit_of_measurement"
MEASUREMENT_ATTR_DOMAIN_DEVICE_CLASS = "domain__device_class"
MEASUREMENT_ATTR_ENTITY_ID = "entity_id"
MEASUREMENT_ATTRS = (
    MEASUREMENT_ATTR_UNIT,
    MEASUREMENT_ATTR_DOMAIN_DEVICE_CLASS,
    MEASUREMENT_ATTR_ENTITY_ID,
)

HEARTBEAT_FIELD = "_heartbeat"
STARTUP_FIELD = "_startup"

SKIPPED_STATES = frozenset({"unknown", "unavailable", ""})

# Copy of homeassistant.helpers.state.state_as_number. A test compares this
# table with the real helper, so a change in Home Assistant is noticed.
_STATES_AS_ONE = frozenset({"on", "locked", "above_horizon", "open", "home"})
_STATES_AS_ZERO = frozenset(
    {"off", "unlocked", "unknown", "below_horizon", "closed", "not_home"}
)

# Same expressions as the core const.py.
_RE_DIGIT_TAIL = re.compile(r"^[^\.]*\d+\.?\d+[^\.]*$")
_RE_DECIMAL = re.compile(r"[^\d.]+")


def state_as_number(state: str) -> float:
    """Coerce a state to a number like Home Assistant does. Raises ValueError."""
    if state in _STATES_AS_ONE:
        return 1.0
    if state in _STATES_AS_ZERO:
        return 0.0
    return float(state)


def _single_line(value: str) -> str:
    """Replace line breaks with spaces (line protocol cannot carry them)."""
    return " ".join(value.splitlines())


@dataclass(slots=True)
class EntityCustomization:
    """Per-entity settings, like the core `component_config` entries."""

    # None means "not set", so a more specific entry only overrides what it sets.
    override_measurement: str | None = None
    ignore_attributes: list[str] | None = None


@dataclass(slots=True)
class SchemaOptions:
    """Options that shape the data, with the same defaults as the core integration."""

    measurement_attr: str = MEASUREMENT_ATTR_UNIT
    default_measurement: str | None = None
    override_measurement: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    tags_attributes: list[str] = field(default_factory=list)
    ignore_attributes: list[str] = field(default_factory=list)
    component_config: dict[str, EntityCustomization] = field(default_factory=dict)
    component_config_domain: dict[str, EntityCustomization] = field(
        default_factory=dict
    )
    component_config_glob: dict[str, EntityCustomization] = field(default_factory=dict)

    def customization(self, entity_id: str) -> EntityCustomization:
        """Merge per-entity settings: domain, then glob, then entity (like EntityValues)."""
        merged = EntityCustomization()
        domain = entity_id.split(".", 1)[0]
        sources: list[EntityCustomization] = []
        if domain in self.component_config_domain:
            sources.append(self.component_config_domain[domain])
        sources.extend(
            value
            for pattern, value in self.component_config_glob.items()
            if fnmatch.fnmatchcase(entity_id, pattern)
        )
        if entity_id in self.component_config:
            sources.append(self.component_config[entity_id])
        for source in sources:
            if source.override_measurement is not None:
                merged.override_measurement = source.override_measurement
            if source.ignore_attributes is not None:
                merged.ignore_attributes = list(source.ignore_attributes)
        return merged


_CUSTOMIZATION_KEYS = ("override_measurement", "ignore_attributes")
_CUSTOMIZATION_OPTIONS = (
    "component_config",
    "component_config_domain",
    "component_config_glob",
)


def parse_customizations(value: Any) -> dict[str, EntityCustomization]:
    """Check and convert one `component_config*` mapping. Raises ValueError.

    Expected form, like the core YAML:
    `{"sensor.x": {"override_measurement": "m", "ignore_attributes": ["a"]}}`.
    """
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("expected a mapping")
    result: dict[str, EntityCustomization] = {}
    for key, settings in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("keys must be non-empty strings")
        if settings is None:
            settings = {}
        if not isinstance(settings, Mapping):
            raise ValueError(f"{key}: expected a mapping")
        unknown = set(settings) - set(_CUSTOMIZATION_KEYS)
        if unknown:
            raise ValueError(f"{key}: unknown keys {sorted(unknown)}")
        override = settings.get("override_measurement")
        if override is not None and not isinstance(override, str):
            raise ValueError(f"{key}: override_measurement must be a string")
        ignore = settings.get("ignore_attributes")
        if ignore is not None and (
            not isinstance(ignore, list) or not all(isinstance(a, str) for a in ignore)
        ):
            raise ValueError(f"{key}: ignore_attributes must be a list of strings")
        result[key] = EntityCustomization(
            override_measurement=override, ignore_attributes=ignore
        )
    return result


def schema_options_from(options: Mapping[str, Any]) -> SchemaOptions:
    """Build SchemaOptions from stored entry options. Missing keys use core defaults."""
    return SchemaOptions(
        measurement_attr=options.get("measurement_attr") or MEASUREMENT_ATTR_UNIT,
        default_measurement=options.get("default_measurement") or None,
        override_measurement=options.get("override_measurement") or None,
        tags=dict(options.get("tags") or {}),
        tags_attributes=list(options.get("tags_attributes") or []),
        ignore_attributes=list(options.get("ignore_attributes") or []),
        **{
            key: parse_customizations(options.get(key))
            for key in _CUSTOMIZATION_OPTIONS
        },
    )


def state_to_point(
    entity_id: str,
    state: str | None,
    attributes: Mapping[str, Any],
    time: datetime,
    options: SchemaOptions,
    *,
    heartbeat: bool = False,
    startup: bool = False,
    number: Callable[[str], float] = state_as_number,
) -> Point | None:
    """Build the point for one state, or None if the state is not written."""
    if state is None or state in SKIPPED_STATES:
        return None

    domain, object_id = entity_id.split(".", 1)

    include_state = include_value = False
    state_value = 0.0
    try:
        state_value = float(state)
        include_value = True
    except ValueError:
        try:
            state_value = float(number(state))
            include_state = include_value = True
        except ValueError:
            include_state = True

    include_uom = True
    include_dc = True
    custom = options.customization(entity_id)
    measurement: Any = custom.override_measurement
    if measurement in (None, ""):
        if options.override_measurement:
            measurement = options.override_measurement
        else:
            attr = options.measurement_attr
            if attr == MEASUREMENT_ATTR_ENTITY_ID:
                measurement = entity_id
            elif attr == MEASUREMENT_ATTR_DOMAIN_DEVICE_CLASS:
                device_class = attributes.get("device_class")
                if device_class is None:
                    measurement = domain
                else:
                    measurement = f"{domain}__{device_class}"
                    include_dc = False
            else:
                measurement = attributes.get(attr)
            if measurement in (None, ""):
                measurement = options.default_measurement or entity_id
            else:
                include_uom = attr != MEASUREMENT_ATTR_UNIT

    if isinstance(measurement, str):
        measurement = _single_line(measurement)

    tags: dict[str, Any] = {"domain": domain, "entity_id": object_id}
    fields: dict[str, FieldValue] = {}
    if include_state:
        fields["state"] = _single_line(state)
    if include_value:
        fields["value"] = state_value

    ignore = set(custom.ignore_attributes or ()) | set(options.ignore_attributes)
    for key, value in attributes.items():
        if key in options.tags_attributes:
            tags[key] = _single_line(value) if isinstance(value, str) else value
            continue
        if (
            (key == "unit_of_measurement" and not include_uom)
            or (key == "device_class" and not include_dc)
            or key in ignore
        ):
            continue
        if key in fields:
            key = f"{key}_"
        try:
            fields[key] = float(value)
        except (ValueError, TypeError):
            text = _single_line(str(value))
            fields[f"{key}_str"] = text
            if _RE_DIGIT_TAIL.match(text):
                fields[key] = float(_RE_DECIMAL.sub("", text))
        existing = fields.get(key)
        if isinstance(existing, float) and not math.isfinite(existing):
            del fields[key]

    if "time" in fields:
        new_key = "time_"
        while new_key in fields:
            new_key += "_"
        fields[new_key] = fields.pop("time")

    tags.update({key: _single_line(value) for key, value in options.tags.items()})

    if heartbeat:
        fields[HEARTBEAT_FIELD] = True
    if startup:
        fields[STARTUP_FIELD] = True

    return Point(
        measurement=str(measurement),
        time=time,
        tags={
            k: v if isinstance(v, str) else str(v)
            for k, v in tags.items()
            if v is not None
        },
        fields=fields,
    )
