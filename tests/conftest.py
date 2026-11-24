"""Shared test fixtures."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import label_registry as lr
import pytest

from custom_components.series_picker.point import Point

BACKEND = "custom_components.series_picker.backends.v2.InfluxDB2Backend"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/series_picker in every test."""
    return


class Written:
    """Collects every point the backend is asked to write."""

    def __init__(self) -> None:
        self.points: list[Point] = []

    async def __call__(self, points) -> None:
        self.points.extend(points)

    def entities(self) -> list[tuple[str, bool]]:
        """(entity object id, is heartbeat) per written point."""
        return [
            (p.tags["entity_id"], p.fields.get("_heartbeat", False))
            for p in self.points
        ]

    def clear(self) -> None:
        self.points.clear()


@pytest.fixture
def written():
    """Patch the v2 backend: validation passes, writes are recorded."""
    rec = Written()

    async def write(_self, points):
        await rec(points)

    with (
        patch(f"{BACKEND}.validate", AsyncMock()),
        patch(f"{BACKEND}.write", write),
    ):
        yield rec


@pytest.fixture
def labels(hass: HomeAssistant) -> tuple[str, str]:
    """Create the two labels and return their IDs."""
    reg = lr.async_get(hass)
    change = reg.async_create("Influx").label_id
    heartbeat = reg.async_create("Influx heartbeat").label_id
    return change, heartbeat


if sys.platform == "win32":
    # Home Assistant does not support Windows. To run the tests there anyway
    # (development only), the asyncio event loop needs a local socket pair,
    # which the socket blocker of the test harness forbids. CI runs on Linux
    # with the blocker active.
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
