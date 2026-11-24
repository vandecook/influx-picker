"""Tests for the manual lists, the overview and the repairs issue (M3)."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    label_registry as lr,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.series_picker.const import DOMAIN
from custom_components.series_picker.issues import issue_id
from custom_components.series_picker.repairs import async_create_fix_flow
from custom_components.series_picker.selection import (
    Mode,
    Source,
    Status,
    compute_details,
    label_lists,
    manual_status,
)

from .conftest import Written
from .test_init import DATA, _entity, _flush, _setup

SETUP = "custom_components.series_picker.async_setup_entry"


def _options(labels, **extra) -> dict:
    return {
        "label_change": [labels[0]],
        "label_heartbeat": [labels[1]],
        "heartbeat_interval": 15,
        "inherit_labels": True,
        "startup_snapshot": "now",
        **extra,
    }


# --- selection -------------------------------------------------------------


async def test_manual_merge_and_sources(hass: HomeAssistant, labels) -> None:
    """Union of labels and manual lists; heartbeat wins; sources are kept."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "d")}
    )
    dr.async_get(hass).async_update_device(device.id, labels={labels[0]})
    _entity(hass, "on_device", device_id=device.id)
    labelled = _entity(hass, "labelled")
    er.async_get(hass).async_update_entity(labelled.entity_id, labels={labels[0]})
    off = _entity(hass, "off")
    er.async_get(hass).async_update_entity(
        off.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    hass.states.async_set("sensor.no_unique_id", "1")

    details = compute_details(
        hass,
        _options(
            labels,
            manual_change=["sensor.no_unique_id", "sensor.off"],
            manual_heartbeat=["sensor.labelled", "sensor.gone"],
        ),
    )
    assert {e: (d.mode, d.sources) for e, d in details.items()} == {
        "sensor.on_device": (Mode.CHANGE, {Source.DEVICE}),
        "sensor.labelled": (Mode.HEARTBEAT, {Source.LABEL, Source.MANUAL}),
        "sensor.no_unique_id": (Mode.CHANGE, {Source.MANUAL}),
        # Not there (yet): kept, so it is written as soon as it appears.
        "sensor.gone": (Mode.HEARTBEAT, {Source.MANUAL}),
    }
    assert manual_status(hass, "sensor.no_unique_id") is Status.OK
    assert manual_status(hass, "sensor.off") is Status.DISABLED
    assert manual_status(hass, "sensor.gone") is Status.MISSING


async def test_several_labels_per_mode(hass: HomeAssistant, labels) -> None:
    """Each field can hold several labels; any of them selects the entity."""
    extra = lr.async_get(hass).async_create("Influx extra").label_id
    first = _entity(hass, "first")
    second = _entity(hass, "second")
    both = _entity(hass, "both")
    reg = er.async_get(hass)
    reg.async_update_entity(first.entity_id, labels={labels[0]})
    reg.async_update_entity(second.entity_id, labels={extra})
    reg.async_update_entity(both.entity_id, labels={extra, labels[1]})
    options = {**_options(labels), "label_change": [labels[0], extra]}
    details = compute_details(hass, options)
    assert details[first.entity_id].mode is Mode.CHANGE
    assert details[second.entity_id].mode is Mode.CHANGE
    assert details[both.entity_id].mode is Mode.HEARTBEAT


def test_label_lists_reads_old_single_values() -> None:
    """Up to 0.1.0 a label option held one label ID as a string."""
    assert label_lists({"label_change": "a", "label_heartbeat": None}) == (["a"], [])
    assert label_lists({"label_change": ["a", "b"]}) == (["a", "b"], [])
    assert label_lists({}) == ([], [])


async def test_old_single_label_options_still_select(
    hass: HomeAssistant, labels
) -> None:
    """Entries saved with single label IDs keep working."""
    entity = _entity(hass, "old")
    er.async_get(hass).async_update_entity(entity.entity_id, labels={labels[1]})
    options = {
        **_options(labels),
        "label_change": labels[0],
        "label_heartbeat": labels[1],
    }
    assert compute_details(hass, options)[entity.entity_id].mode is Mode.HEARTBEAT


async def test_manual_entity_is_written(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """An entity without unique ID: snapshot, changes, and late appearance."""
    hass.states.async_set("sensor.yaml", "1")
    await _setup(
        hass, labels, manual_change=["sensor.yaml"], manual_heartbeat=["sensor.late"]
    )
    await _flush(hass)
    assert written.entities() == [("yaml", True)]

    written.clear()
    hass.states.async_set("sensor.yaml", "2")
    hass.states.async_set("sensor.late", "3")
    await _flush(hass)
    assert written.entities() == [("yaml", False), ("late", False)]


# --- options flow ----------------------------------------------------------


def _entry(hass: HomeAssistant, labels, **extra) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="ha", data=DATA, options=_options(labels, **extra)
    )
    entry.add_to_hass(hass)
    return entry


async def _open(hass: HomeAssistant, entry: MockConfigEntry, step: str):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["selection", "manual", "overview", "data_format"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def test_options_manual_list(hass: HomeAssistant, labels) -> None:
    """Both lists are saved; the hints show missing and label-selected entries."""
    labelled = _entity(hass, "labelled")
    er.async_get(hass).async_update_entity(labelled.entity_id, labels={labels[0]})
    hass.states.async_set("sensor.a", "1")
    entry = _entry(
        hass, labels, manual_change=["sensor.labelled", "sensor.gone"], other="kept"
    )
    result = await _open(hass, entry, "manual")
    assert result["step_id"] == "manual"
    assert result["description_placeholders"] == {
        "missing": "`sensor.gone`",
        "by_label": "`sensor.labelled`",
    }
    # Cleanup is offered because an entry is missing.
    assert "remove_missing" in [str(k) for k in result["data_schema"].schema]

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "manual_change": ["sensor.a", "sensor.gone"],
                "manual_heartbeat": ["sensor.labelled"],
                "remove_missing": True,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["manual_change"] == ["sensor.a"]
    assert entry.options["manual_heartbeat"] == ["sensor.labelled"]
    assert entry.options["other"] == "kept"


async def test_options_manual_errors(hass: HomeAssistant, labels) -> None:
    """Same entity in both lists, or nothing selected at all, is refused."""
    entry = _entry(hass, labels)
    result = await _open(hass, entry, "manual")
    assert "remove_missing" not in [str(k) for k in result["data_schema"].schema]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"manual_change": ["sensor.a"], "manual_heartbeat": ["sensor.a"]},
    )
    assert result["errors"] == {"base": "manual_in_both"}

    no_labels = MockConfigEntry(
        domain=DOMAIN,
        data=DATA,
        options={**_options(labels), "label_change": None, "label_heartbeat": None},
    )
    no_labels.add_to_hass(hass)
    result = await _open(hass, no_labels, "manual")
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["errors"] == {"base": "nothing_selected"}


async def test_options_labels_optional_with_manual_list(
    hass: HomeAssistant, labels
) -> None:
    """With manual entries, the labels may be cleared."""
    entry = _entry(hass, labels, manual_change=["sensor.a"])
    result = await _open(hass, entry, "selection")
    new = {k: v for k, v in _options(labels).items() if not k.startswith("label_")}
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["label_change"] == []
    assert entry.options["manual_change"] == ["sensor.a"]


async def test_options_overview(hass: HomeAssistant, labels) -> None:
    """Counts by source and mode, one line per entity, status of manual ones."""
    labelled = _entity(hass, "labelled")
    er.async_get(hass).async_update_entity(labelled.entity_id, labels={labels[1]})
    off = _entity(hass, "off")
    er.async_get(hass).async_update_entity(
        off.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    hass.states.async_set("sensor.yaml", "1")
    entry = _entry(
        hass,
        labels,
        manual_change=["sensor.yaml", "sensor.labelled", "sensor.off", "sensor.gone"],
    )
    result = await _open(hass, entry, "overview")
    assert result["step_id"] == "overview"
    placeholders = result["description_placeholders"]
    assert placeholders == {
        "total": "3",
        "change": "2",
        "heartbeat": "1",
        "label": "1",
        "device": "0",
        "area": "0",
        "manual": "3",
        "missing": "1",
        "disabled": "1",
        "entities": "\n".join(
            [
                "- `sensor.gone`: manual · change · **missing**",
                "- `sensor.labelled`: label, manual · heartbeat",
                "- `sensor.yaml`: manual · change",
                "- `sensor.off`: manual · **disabled**",
            ]
        ),
    }
    # Submitting goes back to the menu.
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.MENU


async def test_overview_german_and_shortened(hass: HomeAssistant, labels) -> None:
    """Words follow the server language; long lists are shortened."""
    await hass.config.async_update(language="de")
    for i in range(105):
        hass.states.async_set(f"sensor.s{i:03}", "1")
    entry = _entry(hass, labels, manual_change=[f"sensor.s{i:03}" for i in range(105)])
    result = await _open(hass, entry, "overview")
    lines = result["description_placeholders"]["entities"].splitlines()
    assert lines[0] == "- `sensor.s000`: manuell · Änderung"
    assert len(lines) == 101
    assert lines[-1] == "- … (+5 weitere)"


# --- rename, repairs -------------------------------------------------------


async def test_renamed_entity_follows(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Renaming an entity ID updates the manual list."""
    old = _entity(hass, "old")
    entry = await _setup(hass, labels, manual_heartbeat=["sensor.old"])
    er.async_get(hass).async_update_entity(old.entity_id, new_entity_id="sensor.new")
    await hass.async_block_till_done()
    assert entry.options["manual_heartbeat"] == ["sensor.new"]
    assert "sensor.new" in entry.runtime_data.runtime.tracked


async def test_missing_issue_after_start(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """The issue appears only once Home Assistant has started."""
    hass.set_state(CoreState.starting)
    entry = await _setup(hass, labels, manual_change=["sensor.gone"])
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is None

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    issue = issues.async_get_issue(DOMAIN, issue_id(entry.entry_id))
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders["entities"] == "- `sensor.gone`"

    # The entity appears: the issue goes away with the next check.
    hass.states.async_set("sensor.gone", "1")
    await hass.async_block_till_done()
    await _wait_rebuild(hass)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is None


async def _wait_rebuild(hass: HomeAssistant) -> None:
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


async def test_state_removed_raises_issue(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """A manual entity without registry entry that disappears is reported."""
    hass.states.async_set("sensor.yaml", "1")
    entry = await _setup(hass, labels, manual_change=["sensor.yaml"])
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is None
    hass.states.async_remove("sensor.yaml")
    await hass.async_block_till_done()
    await _wait_rebuild(hass)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is not None


async def test_fix_flow_removes_missing(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """The repairs fix flow removes the missing entries; the issue goes away."""
    hass.states.async_set("sensor.yaml", "1")
    entry = await _setup(hass, labels, manual_change=["sensor.yaml", "sensor.gone"])
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, issue_id(entry.entry_id))
    assert issue is not None

    flow = await async_create_fix_flow(hass, issue.issue_id, issue.data)
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "test"
    result = await flow.async_step_init()
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["entities"] == "- `sensor.gone`"
    result = await flow.async_step_confirm({})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options["manual_change"] == ["sensor.yaml"]
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is None


async def test_removed_entry_deletes_issue(
    hass: HomeAssistant, written: Written, labels
) -> None:
    """Removing the entry removes its issue."""
    entry = await _setup(hass, labels, manual_change=["sensor.gone"])
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is not None
    await hass.config_entries.async_remove(entry.entry_id)
    assert issues.async_get_issue(DOMAIN, issue_id(entry.entry_id)) is None
