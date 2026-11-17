"""Shared test fixtures."""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/influx_picker in every test."""
    return


if sys.platform == "win32":
    # Home Assistant does not support Windows. To run the tests there anyway
    # (development only), the asyncio event loop needs a local socket pair,
    # which the socket blocker of the test harness forbids. CI runs on Linux
    # with the blocker active.
    import pytest_socket

    pytest_socket.disable_socket = lambda *args, **kwargs: None
