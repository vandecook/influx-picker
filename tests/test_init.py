"""Tests for setup, label selection, snapshots, heartbeat and unload."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.influx_picker.backends import (
    BackendAuthError,
    BackendConnectionError,
)
from custom_components.influx_picker.const import DOMAIN

from .conftest import Written

BACKEND = "custom_components.influx_picker.backends.v2.InfluxDB2Backend"

DATA = {
    "backend": "v2",
    "url": "http://influx.test:8086",
    "organization": "home",
    "bucket": "ha",
    "token": "secret-token",
    "verify_ssl": True,
}


def _entity(hass: HomeAssistant, object_id: str, **kwargs) -> er.RegistryEntry:
    return er.async_get(hass).async_get_or_create(
        "sensor", "test", object_id, suggested_object_id=object_id, **kwargs
    )


async def _setup(
    hass: HomeAssistant, labels: tuple[str, str], **options
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ha",
        data=DATA,
        options={
            "label_change": labels[0],
            "label_heartbeat": labels[1],
            "heartbeat_interval": 15,
            "inherit_labels": True,
            **options,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _flush(hass: HomeAssistant) -> None:
    """Let the 1 s batch timeout pass (real time is short-circuited by firing time)."""
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    exporter = entry.runtime_data.exporter
    # Write everything queued right now, without waiting for the quiet period.
    while exporter.queue_size:
        await exporter._write_one_batch()


async def test_snapshot_and_changes(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Labelled entities get a snapshot at setup and are written on change."""
    a = _entity(hass, "a")
    b = _entity(hass, "b")
    _entity(hass, "untracked")
    er.async_get(hass).async_update_entity(a.entity_id, labels={labels[0]})
    er.async_get(hass).async_update_entity(b.entity_id, labels={labels[1]})
    for eid in ("sensor.a", "sensor.b", "sensor.untracked"):
        hass.states.async_set(eid, "1")

    entry = await _setup(hass, labels)
    assert entry.state is ConfigEntryState.LOADED
    await _flush(hass)
    assert sorted(written.entities()) == [("a", True), ("b", True)]

    written.clear()
    hass.states.async_set("sensor.a", "2")
    hass.states.async_set("sensor.untracked", "2")
    hass.states.async_set("sensor.b", "unavailable")
    await _flush(hass)
    assert written.entities() == [("a", False)]
    assert written.points[0].fields["value"] == 2.0


async def test_data_format_options_are_used(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Stored data format options shape every point, from the first snapshot on."""
    a = _entity(hass, "a")
    er.async_get(hass).async_update_entity(a.entity_id, labels={labels[0]})
    hass.states.async_set("sensor.a", "on", {"friendly_name": "A"})

    await _setup(
        hass,
        labels,
        default_measurement="units",
        tags={"source": "HA"},
        tags_attributes=["friendly_name"],
    )
    await _flush(hass)
    hass.states.async_set("sensor.a", "off", {"friendly_name": "A"})
    await _flush(hass)

    assert len(written.points) == 2
    for point in written.points:
        assert point.measurement == "units"
        assert point.tags == {
            "domain": "sensor",
            "entity_id": "a",
            "friendly_name": "A",
            "source": "HA",
        }
        assert "friendly_name_str" not in point.fields


async def test_invalid_stored_data_format_fails_setup(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Hand-edited, invalid per-entity settings stop the entry with an error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ha",
        data=DATA,
        options={"label_change": labels[0], "component_config": {"x": "bad"}},
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_startup_snapshot_last_updated(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Option "last_updated": own timestamp, marked _startup, not heartbeat."""
    a = _entity(hass, "a")
    er.async_get(hass).async_update_entity(a.entity_id, labels={labels[1]})
    hass.states.async_set("sensor.a", "1")
    last_updated = hass.states.get("sensor.a").last_updated
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))

    await _setup(hass, labels, startup_snapshot="last_updated")
    await _flush(hass)
    assert len(written.points) == 1
    point = written.points[0]
    assert point.time == last_updated
    assert point.fields["_startup"] is True
    assert "_heartbeat" not in point.fields

    # Entities selected later still get the normal heartbeat snapshot.
    written.clear()
    b = _entity(hass, "b")
    hass.states.async_set("sensor.b", "2")
    er.async_get(hass).async_update_entity(b.entity_id, labels={labels[0]})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await _flush(hass)
    assert written.entities() == [("b", True)]
    assert "_startup" not in written.points[0].fields


async def test_startup_snapshot_off(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Option "off": nothing at start, changes and later selections still work."""
    a = _entity(hass, "a")
    er.async_get(hass).async_update_entity(a.entity_id, labels={labels[1]})
    hass.states.async_set("sensor.a", "1")

    await _setup(hass, labels, startup_snapshot="off")
    await _flush(hass)
    assert written.points == []

    # The heartbeat clock starts at setup: no heartbeat before the interval.
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.runtime_data.runtime._async_heartbeat(dt_util.utcnow())
    await _flush(hass)
    assert written.points == []

    hass.states.async_set("sensor.a", "2")
    await _flush(hass)
    assert written.entities() == [("a", False)]

    written.clear()
    b = _entity(hass, "b")
    hass.states.async_set("sensor.b", "2")
    er.async_get(hass).async_update_entity(b.entity_id, labels={labels[0]})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await _flush(hass)
    assert written.entities() == [("b", True)]


async def test_label_added_at_runtime(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Adding a label takes effect without a restart (after the debounce)."""
    c = _entity(hass, "c")
    hass.states.async_set("sensor.c", "5")
    await _setup(hass, labels)
    await _flush(hass)
    assert written.points == []

    er.async_get(hass).async_update_entity(c.entity_id, labels={labels[0]})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await _flush(hass)
    assert written.entities() == [("c", True)]

    written.clear()
    er.async_get(hass).async_update_entity(c.entity_id, labels=set())
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    hass.states.async_set("sensor.c", "6")
    await _flush(hass)
    assert written.points == []


async def test_inheritance_from_device_and_area(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Device and area labels apply to entities, unless switched off."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    area = ar.async_get(hass).async_create("Kitchen", labels={labels[0]})
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "dev1")}
    )
    dr.async_get(hass).async_update_device(device.id, labels={labels[1]})
    _entity(hass, "on_device", device_id=device.id)
    in_area = _entity(hass, "in_area")
    er.async_get(hass).async_update_entity(in_area.entity_id, area_id=area.id)
    for eid in ("sensor.on_device", "sensor.in_area"):
        hass.states.async_set(eid, "1")

    entry = await _setup(hass, labels)
    await _flush(hass)
    assert sorted(written.entities()) == [("in_area", True), ("on_device", True)]
    from custom_components.influx_picker.selection import Mode

    assert entry.runtime_data.runtime.tracked == {
        "sensor.on_device": Mode.HEARTBEAT,
        "sensor.in_area": Mode.CHANGE,
    }


async def test_inheritance_off(hass: HomeAssistant, written: Written, labels) -> None:
    """With inheritance off, only the entity's own labels count."""
    area = ar.async_get(hass).async_create("Kitchen", labels={labels[0]})
    in_area = _entity(hass, "in_area")
    er.async_get(hass).async_update_entity(in_area.entity_id, area_id=area.id)
    entry = await _setup(hass, labels, inherit_labels=False)
    assert entry.runtime_data.runtime.tracked == {}


async def test_disabled_entity_and_heartbeat_wins(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Disabled entities are skipped; both labels means heartbeat mode."""
    reg = er.async_get(hass)
    off = _entity(hass, "off", disabled_by=er.RegistryEntryDisabler.USER)
    both = _entity(hass, "both")
    reg.async_update_entity(off.entity_id, labels={labels[0]})
    reg.async_update_entity(both.entity_id, labels={labels[0], labels[1]})
    entry = await _setup(hass, labels)
    from custom_components.influx_picker.selection import Mode

    assert entry.runtime_data.runtime.tracked == {"sensor.both": Mode.HEARTBEAT}


async def test_heartbeat_cycle(hass: HomeAssistant, written: Written, labels) -> None:
    """Heartbeat entities are rewritten after the interval; change entities never."""
    reg = er.async_get(hass)
    reg.async_update_entity(_entity(hass, "hb").entity_id, labels={labels[1]})
    reg.async_update_entity(_entity(hass, "ch").entity_id, labels={labels[0]})
    hass.states.async_set("sensor.hb", "1")
    hass.states.async_set("sensor.ch", "1")
    entry = await _setup(hass, labels, heartbeat_interval=15)
    runtime = entry.runtime_data.runtime
    now = [1000.0]
    runtime._clock = lambda: now[0]
    runtime._last_write = dict.fromkeys(runtime.tracked, 1000.0)
    await _flush(hass)
    written.clear()

    now[0] += 10 * 60  # 10 minutes: too early
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await _flush(hass)
    assert written.points == []

    now[0] += 6 * 60  # 16 minutes since the last write
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=122))
    await _flush(hass)
    assert written.entities() == [("hb", True)]

    # A change resets the clock.
    written.clear()
    now[0] += 14 * 60
    hass.states.async_set("sensor.hb", "2")
    await hass.async_block_till_done()
    now[0] += 2 * 60  # 16 min after the heartbeat, 2 min after the change
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=183))
    await _flush(hass)
    assert written.entities() == [("hb", False)]


async def test_unload_flushes(hass: HomeAssistant, written: Written, labels) -> None:
    """Unloading writes what is still queued."""
    reg = er.async_get(hass)
    reg.async_update_entity(_entity(hass, "a").entity_id, labels={labels[0]})
    hass.states.async_set("sensor.a", "1")
    entry = await _setup(hass, labels)
    hass.states.async_set("sensor.a", "2")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert [p.fields["value"] for p in written.points] == [1.0, 2.0]


async def test_setup_retries_when_server_is_down(hass: HomeAssistant, labels) -> None:
    """A connection problem at setup means "retry later"."""
    with patch(
        f"{BACKEND}.validate", AsyncMock(side_effect=BackendConnectionError("x"))
    ):
        entry = MockConfigEntry(domain=DOMAIN, data=DATA, options={})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_fails_on_bad_token(hass: HomeAssistant, labels) -> None:
    """A rejected token stops setup and asks the user for a new one."""
    with patch(f"{BACKEND}.validate", AsyncMock(side_effect=BackendAuthError("x"))):
        entry = MockConfigEntry(domain=DOMAIN, data=DATA, options={})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_token_rejected_while_running(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """A 401 while running starts re-authentication.

    Queued points survive the reload and are written with the new token.
    """
    c = _entity(hass, "c")
    er.async_get(hass).async_update_entity(c.entity_id, labels={labels[0]})
    hass.states.async_set("sensor.c", "1")

    async def write(self, points):
        # Only the new token is accepted.
        if self._config["token"] != "new-token":
            raise BackendAuthError("HTTP 401")
        await written(points)

    with patch(f"{BACKEND}.write", write):
        entry = await _setup(hass, labels, startup_snapshot="off")
        hass.states.async_set("sensor.c", "2")
        await hass.async_block_till_done()
        assert not await entry.runtime_data.exporter._write_one_batch()
        await hass.async_block_till_done()
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert [f["context"]["source"] for f in flows] == ["reauth"]

        # The user enters a new token; the entry reloads. The flush during
        # unload still uses the old token and fails, so the point is kept
        # for the next setup.
        result = await hass.config_entries.flow.async_configure(
            flows[0]["flow_id"], {"token": "new-token"}
        )
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()

        assert entry.data["token"] == "new-token"
        await _flush(hass)
    assert [p.fields["value"] for p in written.points] == [2.0]


async def test_removed_entry_forgets_kept_points(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Points kept for a reload are dropped when the entry is removed."""
    entry = await _setup(hass, labels)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ["x"]
    await hass.config_entries.async_remove(entry.entry_id)
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_two_instances(hass: HomeAssistant, written: Written, labels) -> None:
    """Two entries with different labels track independently."""
    reg = er.async_get(hass)
    reg.async_update_entity(_entity(hass, "a").entity_id, labels={labels[0]})
    reg.async_update_entity(_entity(hass, "b").entity_id, labels={labels[1]})
    first = await _setup(hass, (labels[0], None))
    second = MockConfigEntry(
        domain=DOMAIN,
        title="other",
        data={**DATA, "bucket": "other"},
        options={
            "label_change": labels[1],
            "heartbeat_interval": 15,
            "inherit_labels": True,
        },
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    assert set(first.runtime_data.runtime.tracked) == {"sensor.a"}
    assert set(second.runtime_data.runtime.tracked) == {"sensor.b"}
