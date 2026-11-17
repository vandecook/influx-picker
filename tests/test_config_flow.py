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

    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(flow_id, SELECTION)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ha (influx.test:8086)"
    assert result["data"] == {"backend": "v2", **CONNECTION}
    assert result["options"] == SELECTION
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
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {"label_heartbeat": "hb", "heartbeat_interval": 5, "inherit_labels": False},
        )
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


async def test_options_flow(hass: HomeAssistant) -> None:
    """Labels can be changed later."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"backend": "v2", **CONNECTION},
        options=SELECTION,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    new = {**SELECTION, "label_change": "other", "heartbeat_interval": 30}
    with patch(SETUP, return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], new
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == new
