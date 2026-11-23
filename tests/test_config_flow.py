"""Tests for the config flow and the options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.influx_picker.backends import (
    BackendAuthError,
    BackendConnectionError,
    BackendNotFoundError,
)
from custom_components.influx_picker.const import DOMAIN

VALIDATE = "custom_components.influx_picker.backends.v2.InfluxDB2Backend.validate"
SETUP = "custom_components.influx_picker.async_setup_entry"

CONNECTION = {
    "url": "http://influx.test:8086",
    "organization": "home",
    "bucket": "ha",
    "token": "secret-token",
    "verify_ssl": True,
}
SELECTION = {
    "label_change": "influx",
    "label_heartbeat": "influx_heartbeat",
    "heartbeat_interval": 15,
    "inherit_labels": True,
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
    [(None, None, "no_label"), ("a", "a", "same_label")],
)
async def test_selection_errors(hass: HomeAssistant, change, heartbeat, key) -> None:
    """At least one label, and two different labels."""
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
        {"label_heartbeat": "hb", "heartbeat_interval": 5, "inherit_labels": False},
    )
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["label_change"] is None


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
    new = {**SELECTION, "label_change": "other", "heartbeat_interval": 30}
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
