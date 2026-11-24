"""Tests for the config flow and the options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.series_picker.backends import (
    BackendAuthError,
    BackendConnectionError,
    BackendNotFoundError,
)
from custom_components.series_picker.const import DOMAIN

VALIDATE = "custom_components.series_picker.backends.v2.InfluxDB2Backend.validate"
SETUP = "custom_components.series_picker.async_setup_entry"

CONNECTION = {
    "url": "http://influx.test:8086",
    "organization": "home",
    "bucket": "ha",
    "token": "secret-token",
    "verify_ssl": True,
}
SELECTION = {
    "label_change": ["influx"],
    "label_heartbeat": ["influx_heartbeat"],
    "heartbeat_interval": 15,
    "inherit_labels": True,
    "startup_snapshot": "now",
}
# Data format step left as suggested: core defaults.
DEFAULT_FORMAT = {
    "measurement_attr": "unit_of_measurement",
    "default_measurement": None,
    "override_measurement": None,
    "tags": {},
    "tags_attributes": [],
    "ignore_attributes": [],
    "component_config": {},
    "component_config_domain": {},
    "component_config_glob": {},
}
# The maintainer's core YAML settings, as derived in docs/core-schema-audit.md.
MAINTAINER_FORMAT_INPUT = {
    "measurement_attr": "unit_of_measurement",
    "default_measurement": "units",
    "tags": "source=HA",
    "tags_attributes": ["friendly_name"],
}


async def _to_connection_step(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"backend": "v2"}
    )
    assert result["step_id"] == "connection"
    return result["flow_id"]


async def test_full_flow(hass: HomeAssistant) -> None:
    """Version, connection and labels create one entry."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()) as validate:
        result = await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    validate.assert_awaited_once()
    assert result["step_id"] == "selection"

    result = await hass.config_entries.flow.async_configure(flow_id, SELECTION)
    assert result["step_id"] == "data_format"

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"measurement_attr": "unit_of_measurement"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ha (influx.test:8086)"
    assert result["data"] == {"backend": "v2", **CONNECTION}
    assert result["options"] == {**SELECTION, **DEFAULT_FORMAT}
    assert result["result"].unique_id == "v2|http://influx.test:8086|home|ha"


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (BackendAuthError("x"), "invalid_auth"),
        (BackendNotFoundError("x"), "not_found"),
        (BackendConnectionError("x"), "cannot_connect"),
    ],
)
async def test_connection_errors(hass: HomeAssistant, error, key) -> None:
    """Validation errors are shown on the connection step."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock(side_effect=error)):
        result = await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection"
    assert result["errors"] == {"base": key}


@pytest.mark.parametrize(
    ("change", "heartbeat", "key"),
    [(None, None, "no_label"), (["a"], ["b", "a"], "same_label")],
)
async def test_selection_errors(hass: HomeAssistant, change, heartbeat, key) -> None:
    """At least one label, and no label in both fields."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()):
        await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    user_input = {"heartbeat_interval": 15, "inherit_labels": True}
    if change:
        user_input["label_change"] = change
    if heartbeat:
        user_input["label_heartbeat"] = heartbeat
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["errors"] == {"base": key}


async def test_heartbeat_label_alone_is_enough(hass: HomeAssistant) -> None:
    """Only the heartbeat label is a valid selection."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()):
        await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    await hass.config_entries.flow.async_configure(
        flow_id,
        {"label_heartbeat": ["hb"], "heartbeat_interval": 5, "inherit_labels": False},
    )
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["label_change"] == []


async def test_duplicate_target_aborts(hass: HomeAssistant) -> None:
    """The same URL, org and bucket cannot be added twice."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="v2|http://influx.test:8086|home|ha"
    ).add_to_hass(hass)
    flow_id = await _to_connection_step(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _to_data_format_step(hass: HomeAssistant) -> str:
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()):
        await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    result = await hass.config_entries.flow.async_configure(flow_id, SELECTION)
    assert result["step_id"] == "data_format"
    return flow_id


async def test_data_format_maintainer_settings(hass: HomeAssistant) -> None:
    """The core options of a real setup are stored in their core form."""
    flow_id = await _to_data_format_step(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id, MAINTAINER_FORMAT_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        **SELECTION,
        **DEFAULT_FORMAT,
        "default_measurement": "units",
        "tags": {"source": "HA"},
        "tags_attributes": ["friendly_name"],
    }


async def test_data_format_component_config(hass: HomeAssistant) -> None:
    """Per-entity, per-domain and per-pattern settings are kept as given."""
    flow_id = await _to_data_format_step(hass)
    custom = {
        "component_config": {"sensor.a": {"override_measurement": "m"}},
        "component_config_domain": {"light": {"ignore_attributes": ["effect_list"]}},
        "component_config_glob": {"sensor.*_temp": {"override_measurement": "t"}},
    }
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"tags": "a=b\n\n c = d=e ", **custom}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["tags"] == {"a": "b", "c": "d=e"}
    for key, value in custom.items():
        assert result["options"][key] == value


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({"tags": "no_equals_sign"}, {"tags": "invalid_tags"}),
        ({"tags": "key="}, {"tags": "invalid_tags"}),
        (
            {"component_config": {"sensor.a": {"unknown": 1}}},
            {"component_config": "invalid_component_config"},
        ),
        (
            {"component_config_domain": {"light": "text"}},
            {"component_config_domain": "invalid_component_config"},
        ),
        (
            {"component_config_glob": {"x": {"ignore_attributes": "a"}}},
            {"component_config_glob": "invalid_component_config"},
        ),
    ],
)
async def test_data_format_errors(hass: HomeAssistant, user_input, errors) -> None:
    """Invalid tags and per-entity settings are reported on their field."""
    flow_id = await _to_data_format_step(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "data_format"
    assert result["errors"] == errors


async def test_options_flow(hass: HomeAssistant) -> None:
    """Labels can be changed later; the data format options are kept."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"backend": "v2", **CONNECTION},
        options={**SELECTION, **DEFAULT_FORMAT, "default_measurement": "units"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "selection"}
    )
    assert result["step_id"] == "selection"
    new = {**SELECTION, "label_change": ["other", "more"], "heartbeat_interval": 30}
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {**new, **DEFAULT_FORMAT, "default_measurement": "units"}


async def test_options_flow_data_format(hass: HomeAssistant) -> None:
    """The data format can be changed later; the selection is kept."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"backend": "v2", **CONNECTION},
        options={**SELECTION, **DEFAULT_FORMAT},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "data_format"}
    )
    assert result["step_id"] == "data_format"
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], MAINTAINER_FORMAT_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        **SELECTION,
        **DEFAULT_FORMAT,
        "default_measurement": "units",
        "tags": {"source": "HA"},
        "tags_attributes": ["friendly_name"],
    }


async def test_data_format_domain_device_class(hass: HomeAssistant) -> None:
    """The selector value is mapped to the core option value."""
    flow_id = await _to_data_format_step(hass)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"measurement_attr": "domain_device_class"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["measurement_attr"] == "domain__device_class"


async def test_new_setup_suggests_maintainer_format(hass: HomeAssistant) -> None:
    """A new setup pre-fills the maintainer's usual data format values."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()):
        await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    result = await hass.config_entries.flow.async_configure(flow_id, SELECTION)
    assert result["step_id"] == "data_format"
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested == {
        "default_measurement": "units",
        "tags": "source=HA",
        "tags_attributes": ["friendly_name"],
    }


async def test_options_flow_does_not_suggest_for_existing(
    hass: HomeAssistant,
) -> None:
    """An existing entry with empty data format options shows them empty."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"backend": "v2", **CONNECTION},
        options={**SELECTION, **DEFAULT_FORMAT},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "data_format"}
    )
    assert not any(
        key.description and "suggested_value" in key.description
        for key in result["data_schema"].schema
    )


@pytest.mark.parametrize(
    ("submitted", "stored"),
    [(None, "now"), ("last_updated", "last_updated"), ("off", "off")],
)
async def test_startup_snapshot_option(
    hass: HomeAssistant, submitted: str | None, stored: str
) -> None:
    """The startup snapshot defaults to "now" and can be changed."""
    flow_id = await _to_connection_step(hass)
    with patch(VALIDATE, AsyncMock()):
        await hass.config_entries.flow.async_configure(flow_id, CONNECTION)
    selection = {k: v for k, v in SELECTION.items() if k != "startup_snapshot"}
    if submitted:
        selection["startup_snapshot"] = submitted
    result = await hass.config_entries.flow.async_configure(flow_id, selection)
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"measurement_attr": "unit_of_measurement"}
        )
    assert result["options"]["startup_snapshot"] == stored


def test_translation_keys_valid() -> None:
    """Selector option keys follow the hassfest rule (caught in CI otherwise)."""
    import json
    from pathlib import Path
    import re

    rule = re.compile(r"^(?!.*__)[a-z0-9]+(?:[a-z0-9_-]*[a-z0-9])?$")
    base = Path(__file__).parent.parent / "custom_components" / "series_picker"
    for path in [base / "strings.json", *(base / "translations").glob("*.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        for selector in data.get("selector", {}).values():
            for key in selector.get("options", {}):
                assert rule.match(key), f"{path.name}: {key}"


def _connected_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="ha (influx.test:8086)",
        unique_id="v2|http://influx.test:8086|home|ha",
        data={"backend": "v2", **CONNECTION},
        options={**SELECTION, **DEFAULT_FORMAT},
    )
    entry.add_to_hass(hass)
    return entry


def _defaults(schema) -> dict:
    return {
        str(key): key.default()
        for key in schema.schema
        if callable(getattr(key, "default", None))
    }


async def test_reconfigure_keeps_token_when_empty(hass: HomeAssistant) -> None:
    """Changing the bucket keeps the token, updates title and unique ID."""
    entry = _connected_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    # The stored token is not sent back to the form.
    defaults = _defaults(result["data_schema"])
    assert "token" not in defaults
    assert defaults["bucket"] == "ha"

    new = {**CONNECTION, "bucket": "ha2", "token": ""}
    with patch(VALIDATE, AsyncMock()) as validate, patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
    validate.assert_awaited_once()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {"backend": "v2", **CONNECTION, "bucket": "ha2"}
    assert entry.unique_id == "v2|http://influx.test:8086|home|ha2"
    assert entry.title == "ha2 (influx.test:8086)"
    assert entry.options == {**SELECTION, **DEFAULT_FORMAT}


async def test_reconfigure_new_token_and_own_title(hass: HomeAssistant) -> None:
    """A new token is stored; a title the user chose is kept."""
    entry = _connected_entry(hass)
    hass.config_entries.async_update_entry(entry, title="My Influx")
    result = await entry.start_reconfigure_flow(hass)
    with patch(VALIDATE, AsyncMock()), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, "token": "new-token"}
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["token"] == "new-token"
    assert entry.title == "My Influx"


@pytest.mark.parametrize(
    ("error", "base"),
    [
        (BackendAuthError("401"), "invalid_auth"),
        (BackendNotFoundError("404"), "not_found"),
        (BackendConnectionError("down"), "cannot_connect"),
    ],
)
async def test_reconfigure_errors(hass: HomeAssistant, error, base) -> None:
    """A failed check shows the error and changes nothing."""
    entry = _connected_entry(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(VALIDATE, AsyncMock(side_effect=error)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, "token": "wrong"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": base}
    assert entry.data["token"] == "secret-token"


async def test_reconfigure_to_target_of_other_entry(hass: HomeAssistant) -> None:
    """A target another entry already writes to is refused."""
    entry = _connected_entry(hass)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="v2|http://influx.test:8086|home|other",
        data={"backend": "v2", **CONNECTION, "bucket": "other"},
    ).add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(VALIDATE, AsyncMock()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**CONNECTION, "bucket": "other", "token": ""}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["bucket"] == "ha"


async def test_reauth(hass: HomeAssistant) -> None:
    """Re-authentication asks only for the token and stores it."""
    entry = _connected_entry(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert [str(key) for key in result["data_schema"].schema] == ["token"]

    with patch(VALIDATE, AsyncMock(side_effect=BackendAuthError("401"))):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "still-wrong"}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(VALIDATE, AsyncMock()), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "new-token"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"backend": "v2", **CONNECTION, "token": "new-token"}
