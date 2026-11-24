"""Tests for the InfluxDB 2 backend with a mocked HTTP server."""

from __future__ import annotations

from datetime import UTC, datetime

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.series_picker.backends import (
    BACKENDS,
    BackendAuthError,
    BackendConnectionError,
    BackendInvalidDataError,
    BackendNotFoundError,
    get_backend,
)
from custom_components.series_picker.backends.v2 import InfluxDB2Backend
from custom_components.series_picker.point import Point

CONFIG = {
    "backend": "v2",
    "url": "http://influx.test:8086/",
    "organization": "home",
    "bucket": "ha",
    "token": "secret-token",
    "verify_ssl": True,
}
WRITE_URL = "http://influx.test:8086/api/v2/write"
T = datetime(2026, 11, 17, 12, 0, 0, 123456, tzinfo=UTC)


def _backend(
    aioclient_mock: AiohttpClientMocker, hass: HomeAssistant
) -> InfluxDB2Backend:
    # aioclient_mock replaces Home Assistant's shared session with a mock.
    return InfluxDB2Backend(async_get_clientsession(hass), CONFIG)


def test_registry() -> None:
    """The v2 backend is registered under its key."""
    assert get_backend("v2") is InfluxDB2Backend
    assert "v2" in BACKENDS
    with pytest.raises(KeyError):
        get_backend("v9")


def test_title_and_unique_id() -> None:
    """Title and unique ID come from URL, org and bucket."""
    assert InfluxDB2Backend.title(CONFIG) == "ha (influx.test:8086)"
    assert InfluxDB2Backend.unique_id(CONFIG) == "v2|http://influx.test:8086|home|ha"


async def test_write_request(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A write sends line protocol with token, org, bucket and precision."""
    aioclient_mock.post(WRITE_URL, status=204)
    backend = _backend(aioclient_mock, hass)
    await backend.write(
        [
            Point("m", T, {"entity_id": "a"}, {"value": 1.0}),
            Point("m", T, {"entity_id": "b"}, {}),  # no field: left out
        ]
    )
    assert aioclient_mock.call_count == 1
    _method, url, data, headers = aioclient_mock.mock_calls[0]
    assert url.query == {"org": "home", "bucket": "ha", "precision": "ns"}
    assert headers["Authorization"] == "Token secret-token"
    assert data == b"m,entity_id=a value=1 1794916800123456000"


async def test_write_nothing_sends_nothing(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A batch without writable points makes no request."""
    backend = _backend(aioclient_mock, hass)
    await backend.write([Point("m", T, {}, {})])
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, BackendInvalidDataError),
        (413, BackendInvalidDataError),
        (422, BackendInvalidDataError),
        (401, BackendAuthError),
        (403, BackendAuthError),
        (404, BackendNotFoundError),
        (429, BackendConnectionError),
        (500, BackendConnectionError),
        (503, BackendConnectionError),
    ],
)
async def test_write_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status, error
) -> None:
    """HTTP status codes map to the right error class."""
    aioclient_mock.post(WRITE_URL, status=status, text="nope")
    with pytest.raises(error):
        await _backend(aioclient_mock, hass).write([Point("m", T, {}, {"v": 1.0})])


@pytest.mark.parametrize("exc", [aiohttp.ClientError(), TimeoutError()])
async def test_network_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, exc
) -> None:
    """Network problems are temporary errors."""
    aioclient_mock.post(WRITE_URL, exc=exc)
    with pytest.raises(BackendConnectionError):
        await _backend(aioclient_mock, hass).write([Point("m", T, {}, {"v": 1.0})])


@pytest.mark.parametrize("status", [204, 400])
async def test_validate_ok(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status
) -> None:
    """An empty write answered with 204 or 400 means the target is writable."""
    aioclient_mock.post(WRITE_URL, status=status)
    await _backend(aioclient_mock, hass).validate()


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, BackendAuthError),
        (404, BackendNotFoundError),
        (500, BackendConnectionError),
    ],
)
async def test_validate_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status, error
) -> None:
    """Validation reports auth, missing target and server problems."""
    aioclient_mock.post(WRITE_URL, status=status)
    with pytest.raises(error):
        await _backend(aioclient_mock, hass).validate()
