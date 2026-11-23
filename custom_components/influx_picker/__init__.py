"""Influx Picker: write label-selected Home Assistant entities to InfluxDB."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .backends import (
    Backend,
    BackendAuthError,
    BackendError,
    get_backend,
)
from .const import CONF_BACKEND, CONF_VERIFY_SSL, SHUTDOWN_FLUSH_TIMEOUT
from .exporter import Exporter
from .runtime import PickerRuntime
from .schema import schema_options_from


@dataclass(slots=True)
class PickerData:
    """Runtime data of one config entry."""

    backend: Backend
    exporter: Exporter
    runtime: PickerRuntime


type PickerConfigEntry = ConfigEntry[PickerData]


def create_backend(hass: HomeAssistant, data: dict) -> Backend:
    """Create the backend for entry data (also used by the config flow)."""
    backend_cls = get_backend(data[CONF_BACKEND])
    session = async_get_clientsession(hass, verify_ssl=data.get(CONF_VERIFY_SSL, True))
    return backend_cls(session, data)


async def async_setup_entry(hass: HomeAssistant, entry: PickerConfigEntry) -> bool:
    """Set up one export target."""
    backend = create_backend(hass, dict(entry.data))
    try:
        await backend.validate()
    except BackendAuthError as err:
        # No reauth flow yet (planned with the connection options in M7).
        raise ConfigEntryError(str(err)) from err
    except BackendError as err:
        raise ConfigEntryNotReady(str(err)) from err

    exporter = Exporter(backend.write, name=entry.title)
    try:
        schema_options = schema_options_from(entry.options)
    except ValueError as err:
        # The flows validate these options; this only guards hand-edited storage.
        raise ConfigEntryError(f"Invalid data format options: {err}") from err
    runtime = PickerRuntime(hass, entry.options, exporter, schema_options)
    entry.runtime_data = PickerData(backend, exporter, runtime)

    exporter.start()
    runtime.async_start()

    async def _async_on_stop(_event: Event) -> None:
        runtime.async_stop()
        await exporter.stop(SHUTDOWN_FLUSH_TIMEOUT)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_stop)
    )
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: PickerConfigEntry) -> None:
    """Apply changed options by reloading the entry (no Home Assistant restart)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PickerConfigEntry) -> bool:
    """Stop listening, flush what is queued, close the backend."""
    data = entry.runtime_data
    data.runtime.async_stop()
    await data.exporter.stop(SHUTDOWN_FLUSH_TIMEOUT)
    await data.backend.close()
    return True
