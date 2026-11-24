"""Tests for the diagnostic sensors."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.series_picker.backends import (
    BackendConnectionError,
    BackendInvalidDataError,
)
from custom_components.series_picker.const import DOMAIN
from custom_components.series_picker.point import Point
from custom_components.series_picker.sensor import SCAN_INTERVAL, SENSORS

from .conftest import Written
from .test_init import _entity, _flush, _setup


def _entity_id(hass: HomeAssistant, entry_id: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_{key}"
    )
    assert entity_id is not None, key
    return entity_id


def _value(hass: HomeAssistant, entry_id: str, key: str) -> str:
    return hass.states.get(_entity_id(hass, entry_id, key)).state


async def _refresh(hass: HomeAssistant) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(1))
    await hass.async_block_till_done()


async def test_sensors_created_as_diagnostics(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """One device per entry with six diagnostic sensors."""
    entry = await _setup(hass, labels)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.name == "ha"
    for description in SENSORS:
        reg_entry = er.async_get(hass).async_get(
            _entity_id(hass, entry.entry_id, description.key)
        )
        assert reg_entry.entity_category is EntityCategory.DIAGNOSTIC
        assert reg_entry.device_id == device.id
    assert (
        len(er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)) == 6
    )


async def test_values_follow_runtime_and_exporter(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Tracked entities, queue, written points and last success."""
    for name in ("a", "b"):
        reg = _entity(hass, name)
        er.async_get(hass).async_update_entity(reg.entity_id, labels={labels[0]})
        hass.states.async_set(reg.entity_id, "1")
    entry = await _setup(hass, labels)
    eid = entry.entry_id
    assert _value(hass, eid, "last_success") == STATE_UNKNOWN
    # The diagnostic sensors carry no label, so only the two test entities count.
    await _refresh(hass)
    assert _value(hass, eid, "tracked_entities") == "2"
    assert _value(hass, eid, "queue_size") == "2"  # snapshots, not written yet

    await _flush(hass)
    await _refresh(hass)
    assert _value(hass, eid, "queue_size") == "0"
    assert _value(hass, eid, "points_written") == "2"
    assert _value(hass, eid, "dropped_points") == "0"
    assert _value(hass, eid, "write_errors") == "0"
    stamp = dt_util.parse_datetime(_value(hass, eid, "last_success"))
    assert stamp is not None
    assert abs((dt_util.utcnow() - stamp).total_seconds()) < 60


async def test_units_are_translated(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Point counters show a unit in the language of Home Assistant."""
    entry = await _setup(hass, labels)
    state = hass.states.get(_entity_id(hass, entry.entry_id, "queue_size"))
    assert state.attributes["unit_of_measurement"] == "points"
    state = hass.states.get(_entity_id(hass, entry.entry_id, "write_errors"))
    assert "unit_of_measurement" not in state.attributes


async def test_errors_and_dropped_points(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Failed writes count as errors; invalid batches as dropped points."""
    reg = _entity(hass, "a")
    er.async_get(hass).async_update_entity(reg.entity_id, labels={labels[0]})
    hass.states.async_set(reg.entity_id, "1")
    entry = await _setup(hass, labels)
    exporter = entry.runtime_data.exporter
    # Stop the background writer so only this test writes, and queue one point.
    exporter._task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await exporter._task
    exporter._task = None
    exporter.take_queue()
    exporter.add(Point("units", dt_util.utcnow(), {"entity_id": "a"}, {"value": 1.0}))

    # The exporter holds the bound write method, so patch it there.
    down = AsyncMock(side_effect=BackendConnectionError("down"))
    with patch.object(exporter, "_write", down):
        assert not await exporter._write_one_batch()
    await _refresh(hass)
    assert _value(hass, entry.entry_id, "write_errors") == "1"
    assert _value(hass, entry.entry_id, "queue_size") == "1"  # kept for retry

    bad = AsyncMock(side_effect=BackendInvalidDataError("bad"))
    with patch.object(exporter, "_write", bad):
        assert await exporter._write_one_batch()
    await _refresh(hass)
    assert _value(hass, entry.entry_id, "dropped_points") == "1"
    assert _value(hass, entry.entry_id, "queue_size") == "0"


async def test_unload_makes_sensors_unavailable(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Unloading the entry unloads the sensor platform too."""
    entry = await _setup(hass, labels)
    entity_id = _entity_id(hass, entry.entry_id, "tracked_entities")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_reload_keeps_sensors(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """After a reload the same sensors are back (counters start at zero)."""
    entry = await _setup(hass, labels)
    entity_id = _entity_id(hass, entry.entry_id, "points_written")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "0"
