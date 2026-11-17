"""Work out which entities are exported, from Home Assistant labels."""

from __future__ import annotations

from enum import IntEnum

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)


class Mode(IntEnum):
    """Export mode. A higher value wins when an entity is selected twice."""

    CHANGE = 1
    HEARTBEAT = 2


def compute_selection(
    hass: HomeAssistant,
    change_label: str | None,
    heartbeat_label: str | None,
    inherit: bool,
) -> dict[str, Mode]:
    """Return entity_id -> mode for every enabled entity that carries a label.

    Labels are label IDs. With `inherit`, labels of the entity's device and of
    its area (the entity's own area, else the device's area) count as well.
    """
    wanted = {
        label: mode
        for label, mode in (
            (change_label, Mode.CHANGE),
            (heartbeat_label, Mode.HEARTBEAT),
        )
        if label
    }
    if not wanted:
        return {}

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)

    result: dict[str, Mode] = {}
    for entry in ent_reg.entities.values():
        if entry.disabled_by is not None:
            continue
        labels = set(entry.labels)
        if inherit:
            device = dev_reg.async_get(entry.device_id) if entry.device_id else None
            if device is not None:
                labels |= device.labels
            area_id = entry.area_id or (device.area_id if device else None)
            if area_id and (area := area_reg.async_get_area(area_id)) is not None:
                labels |= area.labels
        modes = [mode for label, mode in wanted.items() if label in labels]
        if modes:
            result[entry.entity_id] = max(modes)
    return result
