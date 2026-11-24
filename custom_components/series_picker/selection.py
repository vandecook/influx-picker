"""Work out which entities are exported: Home Assistant labels plus manual lists."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    CONF_INHERIT,
    CONF_LABEL_CHANGE,
    CONF_LABEL_HEARTBEAT,
    CONF_MANUAL_CHANGE,
    CONF_MANUAL_HEARTBEAT,
    DEFAULT_INHERIT,
)


class Mode(IntEnum):
    """Export mode. A higher value wins when an entity is selected twice."""

    CHANGE = 1
    HEARTBEAT = 2


class Source(StrEnum):
    """Why an entity is selected."""

    LABEL = "label"  # label on the entity itself
    DEVICE = "device"  # label on its device (inheritance)
    AREA = "area"  # label on its area (inheritance)
    MANUAL = "manual"  # manual list


class Status(StrEnum):
    """State of a manually listed entity."""

    OK = "ok"
    MISSING = "missing"  # neither in the entity registry nor in the state machine
    DISABLED = "disabled"


@dataclass(slots=True)
class Selected:
    """One selected entity."""

    mode: Mode
    sources: set[Source]


def manual_lists(options: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return the two manual lists (change, heartbeat) from entry options."""
    return (
        list(options.get(CONF_MANUAL_CHANGE) or []),
        list(options.get(CONF_MANUAL_HEARTBEAT) or []),
    )


def label_lists(options: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Return the two label ID lists (change, heartbeat) from entry options.

    Up to 0.1.0 each option held a single label ID (a string); that form is
    still read.
    """

    def _ids(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return [v for v in value if v]

    return _ids(options.get(CONF_LABEL_CHANGE)), _ids(options.get(CONF_LABEL_HEARTBEAT))


def manual_status(hass: HomeAssistant, entity_id: str) -> Status:
    """Whether a manually listed entity still exists."""
    entry = er.async_get(hass).async_get(entity_id)
    if entry is not None:
        return Status.DISABLED if entry.disabled_by is not None else Status.OK
    return Status.OK if hass.states.get(entity_id) is not None else Status.MISSING


def missing_manual(hass: HomeAssistant, options: Mapping[str, Any]) -> list[str]:
    """Manually listed entities that no longer exist, sorted."""
    change, heartbeat = manual_lists(options)
    return sorted(
        e
        for e in set(change) | set(heartbeat)
        if manual_status(hass, e) is Status.MISSING
    )


def without_entities(
    options: Mapping[str, Any], remove: Iterable[str]
) -> dict[str, Any]:
    """Options with the given entities removed from both manual lists."""
    gone = set(remove)
    change, heartbeat = manual_lists(options)
    return {
        **options,
        CONF_MANUAL_CHANGE: [e for e in change if e not in gone],
        CONF_MANUAL_HEARTBEAT: [e for e in heartbeat if e not in gone],
    }


def renamed_entity(
    options: Mapping[str, Any], old: str, new: str
) -> dict[str, Any] | None:
    """Options with a renamed entity ID replaced; None if it is not listed."""
    change, heartbeat = manual_lists(options)
    if old not in change and old not in heartbeat:
        return None
    return {
        **options,
        CONF_MANUAL_CHANGE: [new if e == old else e for e in change],
        CONF_MANUAL_HEARTBEAT: [new if e == old else e for e in heartbeat],
    }


def _label_selection(
    hass: HomeAssistant,
    change_labels: list[str],
    heartbeat_labels: list[str],
    inherit: bool,
) -> dict[str, Selected]:
    # Heartbeat wins if a label is in both lists.
    wanted = dict.fromkeys(change_labels, Mode.CHANGE)
    wanted.update(dict.fromkeys(heartbeat_labels, Mode.HEARTBEAT))
    if not wanted:
        return {}

    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    result: dict[str, Selected] = {}
    for entry in er.async_get(hass).entities.values():
        if entry.disabled_by is not None:
            continue
        found: list[tuple[Mode, Source]] = [
            (mode, Source.LABEL)
            for label, mode in wanted.items()
            if label in entry.labels
        ]
        if inherit:
            device = dev_reg.async_get(entry.device_id) if entry.device_id else None
            if device is not None:
                found += [
                    (mode, Source.DEVICE)
                    for label, mode in wanted.items()
                    if label in device.labels
                ]
            area_id = entry.area_id or (device.area_id if device else None)
            if area_id and (area := area_reg.async_get_area(area_id)) is not None:
                found += [
                    (mode, Source.AREA)
                    for label, mode in wanted.items()
                    if label in area.labels
                ]
        if found:
            result[entry.entity_id] = Selected(
                max(mode for mode, _ in found), {source for _, source in found}
            )
    return result


def compute_details(
    hass: HomeAssistant, options: Mapping[str, Any]
) -> dict[str, Selected]:
    """Return entity_id -> mode and sources for every selected entity.

    Labels are label IDs. With inheritance, labels of the entity's device and
    of its area (the entity's own area, else the device's area) count as well.
    Manual entries are merged in (union; heartbeat wins). Disabled entities
    are skipped. Manual entries that do not exist (yet) are kept, so they are
    written as soon as they appear.
    """
    result = _label_selection(
        hass, *label_lists(options), options.get(CONF_INHERIT, DEFAULT_INHERIT)
    )
    change, heartbeat = manual_lists(options)
    for entity_ids, mode in ((change, Mode.CHANGE), (heartbeat, Mode.HEARTBEAT)):
        for entity_id in entity_ids:
            if manual_status(hass, entity_id) is Status.DISABLED:
                continue
            if (sel := result.get(entity_id)) is None:
                result[entity_id] = Selected(mode, {Source.MANUAL})
            else:
                sel.mode = max(sel.mode, mode)
                sel.sources.add(Source.MANUAL)
    return result


def compute_selection(
    hass: HomeAssistant, options: Mapping[str, Any]
) -> dict[str, Mode]:
    """Return entity_id -> mode for every selected entity."""
    return {e: sel.mode for e, sel in compute_details(hass, options).items()}
