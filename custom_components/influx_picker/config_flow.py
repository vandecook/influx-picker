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
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
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
    CONF_COMPONENT_CONFIG,
    CONF_COMPONENT_CONFIG_DOMAIN,
    CONF_COMPONENT_CONFIG_GLOB,
    CONF_DEFAULT_MEASUREMENT,
    CONF_HEARTBEAT_INTERVAL,
    CONF_IGNORE_ATTRIBUTES,
    CONF_INHERIT,
    CONF_LABEL_CHANGE,
    CONF_LABEL_HEARTBEAT,
    CONF_MEASUREMENT_ATTR,
    CONF_OVERRIDE_MEASUREMENT,
    CONF_TAGS,
    CONF_TAGS_ATTRIBUTES,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_INHERIT,
    DOMAIN,
)
from .schema import (
    MEASUREMENT_ATTR_DOMAIN_DEVICE_CLASS,
    MEASUREMENT_ATTR_UNIT,
    MEASUREMENT_ATTRS,
    parse_customizations,
)

_CUSTOMIZATIONS = (
    CONF_COMPONENT_CONFIG,
    CONF_COMPONENT_CONFIG_DOMAIN,
    CONF_COMPONENT_CONFIG_GLOB,
)

# Translation keys may not contain "__", so the selector uses its own value for
# the core option `domain__device_class`. Stored options keep the core value.
_ATTR_TO_UI = {MEASUREMENT_ATTR_DOMAIN_DEVICE_CLASS: "domain_device_class"}
_ATTR_FROM_UI = {ui: core for core, ui in _ATTR_TO_UI.items()}


def _tags_to_text(tags: Mapping[str, str] | None) -> str:
    return "\n".join(f"{key}={value}" for key, value in (tags or {}).items())


def _text_to_tags(text: str | None) -> dict[str, str]:
    """Parse one `key=value` per line. Raises ValueError."""
    tags: dict[str, str] = {}
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value:
            raise ValueError(line)
        tags[key] = value
    return tags


def data_format_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Data format options, same names and defaults as the core integration."""

    def _suggested(value: Any) -> dict[str, Any]:
        return {"suggested_value": value} if value else {}

    free_list = SelectSelector(
        SelectSelectorConfig(
            options=[],
            multiple=True,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )
    tags = defaults.get(CONF_TAGS)
    attr = defaults.get(CONF_MEASUREMENT_ATTR) or MEASUREMENT_ATTR_UNIT
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_MEASUREMENT_ATTR, default=_ATTR_TO_UI.get(attr, attr)
        ): SelectSelector(
            SelectSelectorConfig(
                options=[_ATTR_TO_UI.get(a, a) for a in MEASUREMENT_ATTRS],
                translation_key=CONF_MEASUREMENT_ATTR,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(
            CONF_DEFAULT_MEASUREMENT,
            description=_suggested(defaults.get(CONF_DEFAULT_MEASUREMENT)),
        ): TextSelector(),
        vol.Optional(
            CONF_OVERRIDE_MEASUREMENT,
            description=_suggested(defaults.get(CONF_OVERRIDE_MEASUREMENT)),
        ): TextSelector(),
        vol.Optional(
            CONF_TAGS,
            description=_suggested(
                tags if isinstance(tags, str) else _tags_to_text(tags)
            ),
        ): TextSelector(TextSelectorConfig(multiline=True)),
        vol.Optional(
            CONF_TAGS_ATTRIBUTES,
            description=_suggested(defaults.get(CONF_TAGS_ATTRIBUTES)),
        ): free_list,
        vol.Optional(
            CONF_IGNORE_ATTRIBUTES,
            description=_suggested(defaults.get(CONF_IGNORE_ATTRIBUTES)),
        ): free_list,
    }
    for key in _CUSTOMIZATIONS:
        schema[vol.Optional(key, description=_suggested(defaults.get(key)))] = (
            ObjectSelector()
        )
    return vol.Schema(schema)


def _clean_data_format(
    user_input: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize the data format step. Returns (options, errors)."""
    errors: dict[str, str] = {}
    attr = user_input.get(CONF_MEASUREMENT_ATTR) or MEASUREMENT_ATTR_UNIT
    options: dict[str, Any] = {
        CONF_MEASUREMENT_ATTR: _ATTR_FROM_UI.get(attr, attr),
        CONF_DEFAULT_MEASUREMENT: (
            user_input.get(CONF_DEFAULT_MEASUREMENT) or ""
        ).strip()
        or None,
        CONF_OVERRIDE_MEASUREMENT: (
            user_input.get(CONF_OVERRIDE_MEASUREMENT) or ""
        ).strip()
        or None,
        CONF_TAGS_ATTRIBUTES: [
            a for a in user_input.get(CONF_TAGS_ATTRIBUTES) or [] if a
        ],
        CONF_IGNORE_ATTRIBUTES: [
            a for a in user_input.get(CONF_IGNORE_ATTRIBUTES) or [] if a
        ],
    }
    if options[CONF_MEASUREMENT_ATTR] not in MEASUREMENT_ATTRS:
        errors[CONF_MEASUREMENT_ATTR] = "invalid_measurement_attr"
    try:
        options[CONF_TAGS] = _text_to_tags(user_input.get(CONF_TAGS))
    except ValueError:
        errors[CONF_TAGS] = "invalid_tags"
    for key in _CUSTOMIZATIONS:
        value = user_input.get(key) or {}
        try:
            parse_customizations(value)
        except ValueError:
            errors[key] = "invalid_component_config"
        else:
            options[key] = dict(value)
    return options, errors


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
        self._options: dict[str, Any] = {}

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
                self._options = options
                return await self.async_step_data_format()
        return self.async_show_form(
            step_id="selection",
            data_schema=selection_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_data_format(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Data format, before the first point is written (core defaults)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, errors = _clean_data_format(user_input)
            if not errors:
                backend_cls = get_backend(self._data[CONF_BACKEND])
                return self.async_create_entry(
                    title=backend_cls.title(self._data),
                    data=self._data,
                    options={**self._options, **options},
                )
        return self.async_show_form(
            step_id="data_format",
            data_schema=data_format_schema(user_input or {}),
            errors=errors,
        )


class InfluxPickerOptionsFlow(OptionsFlow):
    """Menu: entity selection or data format."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the menu. Manual lists and the overview join it in M3."""
        return self.async_show_menu(
            step_id="init", menu_options=["selection", "data_format"]
        )

    async def async_step_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change labels, heartbeat interval and inheritance."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, errors = _clean_selection(user_input)
            if not errors:
                return self.async_create_entry(
                    data={**self.config_entry.options, **options}
                )
        return self.async_show_form(
            step_id="selection",
            data_schema=selection_schema(user_input or self.config_entry.options),
            errors=errors,
        )

    async def async_step_data_format(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the data format options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options, errors = _clean_data_format(user_input)
            if not errors:
                return self.async_create_entry(
                    data={**self.config_entry.options, **options}
                )
        return self.async_show_form(
            step_id="data_format",
            data_schema=data_format_schema(user_input or self.config_entry.options),
            errors=errors,
        )
