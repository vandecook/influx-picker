"""Diagnostic sensors of one config entry (tracked entities, queue, errors).

The values live in memory (exporter and runtime) and are read every
`SCAN_INTERVAL`. Counters start at zero when the entry starts (Home Assistant
start or reload of the entry); they use `total_increasing`, so statistics
handle the reset.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PickerConfigEntry, PickerData
from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
PARALLEL_UPDATES = 0  # values are read from memory


@dataclass(frozen=True, kw_only=True)
class PickerSensorDescription(SensorEntityDescription):
    """Describes one diagnostic sensor."""

    value_fn: Callable[[PickerData], int | datetime | None]


def _last_success(data: PickerData) -> datetime | None:
    if (stamp := data.exporter.stats.last_success) is None:
        return None
    return dt_util.utc_from_timestamp(stamp)


SENSORS: tuple[PickerSensorDescription, ...] = (
    PickerSensorDescription(
        key="tracked_entities",
        translation_key="tracked_entities",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: len(data.runtime.tracked),
    ),
    PickerSensorDescription(
        key="queue_size",
        translation_key="queue_size",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.exporter.queue_size,
    ),
    PickerSensorDescription(
        key="points_written",
        translation_key="points_written",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.exporter.stats.written,
    ),
    PickerSensorDescription(
        key="dropped_points",
        translation_key="dropped_points",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.exporter.stats.dropped_overflow + data.exporter.stats.dropped_invalid
        ),
    ),
    PickerSensorDescription(
        key="write_errors",
        translation_key="write_errors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.exporter.stats.write_errors,
    ),
    PickerSensorDescription(
        key="last_success",
        translation_key="last_success",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_last_success,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PickerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the diagnostic sensors of one entry."""
    async_add_entities(PickerSensor(entry, description) for description in SENSORS)


class PickerSensor(SensorEntity):
    """A diagnostic value of one entry, read from memory."""

    entity_description: PickerSensorDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: PickerConfigEntry, description: PickerSensorDescription
    ) -> None:
        """Bind the sensor to its entry."""
        self.entity_description = description
        self._data = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Series Picker",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | datetime | None:
        """Current value."""
        return self.entity_description.value_fn(self._data)
