"""Config flow and options flow for Influx Picker."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LabelSelector,
    LabelSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import create_backend
from ._vol import vol
from .backends import (
    BACKENDS,
    BackendAuthError,
    BackendError,
    BackendNotFoundError,
    get_backend,
)
from .const import (
    CONF_BACKEND,
    CONF_HEARTBEAT_INTERVAL,
    CONF_INHERIT,
    CONF_LABEL_CHANGE,
    CONF_LABEL_HEARTBEAT,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_INHERIT,
    DOMAIN,
)


def selection_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Labels, heartbeat interval and inheritance (config and options flow)."""

    def _default(key: str) -> dict[str, Any]:
        value = defaults.get(key)
        return {"suggested_value": value} if value else {}

    return vol.Schema(
        {
            vol.Optional(
                CONF_LABEL_CHANGE, description=_default(CONF_LABEL_CHANGE)
            ): LabelSelector(LabelSelectorConfig()),
            vol.Optional(
                CONF_LABEL_HEARTBEAT, description=_default(CONF_LABEL_HEARTBEAT)
            ): LabelSelector(LabelSelectorConfig()),
            vol.Required(
                CONF_HEARTBEAT_INTERVAL,
                default=defaults.get(
                    CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=1440,
                    step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_INHERIT, default=defaults.get(CONF_INHERIT, DEFAULT_INHERIT)
            ): bool,
        }
    )


def _clean_selection(user_input: Mapping[str, Any]) -> tuple[dict[str, Any], dict]:
    """Normalize the selection step. Returns (options, errors)."""
    options = {
        CONF_LABEL_CHANGE: user_input.get(CONF_LABEL_CHANGE) or None,
        CONF_LABEL_HEARTBEAT: user_input.get(CONF_LABEL_HEARTBEAT) or None,
        CONF_HEARTBEAT_INTERVAL: int(user_input[CONF_HEARTBEAT_INTERVAL]),
        CONF_INHERIT: bool(user_input[CONF_INHERIT]),
    }
    errors: dict[str, str] = {}
    if not options[CONF_LABEL_CHANGE] and not options[CONF_LABEL_HEARTBEAT]:
        errors["base"] = "no_label"
    elif options[CONF_LABEL_CHANGE] == options[CONF_LABEL_HEARTBEAT]:
        errors["base"] = "same_label"
    return options, errors


class InfluxPickerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Step 1: version. Step 2: connection. Step 3: labels."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with empty data."""
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return InfluxPickerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the InfluxDB version (backend)."""
        if user_input is not None:
            self._data[CONF_BACKEND] = user_input[CONF_BACKEND]
            return await self.async_step_connection()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BACKEND, default="v2"): SelectSelector(
                        SelectSelectorConfig(
                            options=sorted(BACKENDS),
                            translation_key=CONF_BACKEND,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Backend-specific connection fields, checked for real."""
        backend_cls = get_backend(self._data[CONF_BACKEND])
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._data, **user_input}
            if (unique_id := backend_cls.unique_id(data)) is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
            try:
                await create_backend(self.hass, data).validate()
            except BackendAuthError:
                errors["base"] = "invalid_auth"
            except BackendNotFoundError:
                errors["base"] = "not_found"
            except BackendError:
                errors["base"] = "cannot_connect"
            else:
                self._data = data
                return await self.async_step_selection()
        schema = backend_cls.schema(user_input)
        return self.async_show_form(
            step_id="connection", data_schema=schema, errors=errors
        )

    async def async_step_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the labels and the heartbeat interval."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, errors = _clean_selection(user_input)
            if not errors:
                backend_cls = get_backend(self._data[CONF_BACKEND])
                return self.async_create_entry(
                    title=backend_cls.title(self._data),
                    data=self._data,
                    options=options,
                )
        return self.async_show_form(
            step_id="selection",
            data_schema=selection_schema(user_input or {}),
            errors=errors,
        )


class InfluxPickerOptionsFlow(OptionsFlow):
    """Change labels, heartbeat interval and inheritance."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step for now; the menu with manual lists comes in M3."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, errors = _clean_selection(user_input)
            if not errors:
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=selection_schema(user_input or self.config_entry.options),
            errors=errors,
        )
