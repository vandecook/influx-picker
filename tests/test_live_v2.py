"""Integration test against a real InfluxDB 2 server.

Skipped unless INFLUXDB_V2_URL, INFLUXDB_V2_TOKEN, INFLUXDB_V2_ORG and
INFLUXDB_V2_BUCKET are set. CI starts a server in a container for this.
"""

from __future__ import annotations

import asyncio
import csv
from datetime import UTC, datetime
import io
import os

import aiohttp
import pytest

from custom_components.series_picker.backends import (
    BackendAuthError,
    BackendNotFoundError,
)
from custom_components.series_picker.backends.v2 import InfluxDB2Backend
from custom_components.series_picker.schema import SchemaOptions, state_to_point

ENV = {
    "url": os.environ.get("INFLUXDB_V2_URL"),
    "token": os.environ.get("INFLUXDB_V2_TOKEN"),
    "organization": os.environ.get("INFLUXDB_V2_ORG"),
    "bucket": os.environ.get("INFLUXDB_V2_BUCKET"),
}

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not all(ENV.values()), reason="no InfluxDB 2 server configured"),
    # The Home Assistant test harness blocks sockets in its own setup hook and
    # ignores the enable_socket marker. The socket_enabled fixture runs after
    # that hook and allows them again (connections stay limited to 127.0.0.1).
    pytest.mark.usefixtures("socket_enabled"),
]


QUERY_ATTEMPTS = 20
QUERY_DELAY = 0.5  # seconds


async def _query(session: aiohttp.ClientSession, flux: str) -> list[dict]:
    async with session.post(
        f"{ENV['url'].rstrip('/')}/api/v2/query",
        params={"org": ENV["organization"]},
        headers={
            "Authorization": f"Token {ENV['token']}",
            "Content-Type": "application/vnd.flux",
            "Accept": "application/csv",
        },
        data=flux,
    ) as resp:
        resp.raise_for_status()
        text = await resp.text()
    rows = [r for r in csv.DictReader(io.StringIO(text)) if r.get("_field")]
    return rows


async def test_validate_and_write_roundtrip() -> None:
    """Validate, write core-compatible points, read them back."""
    async with aiohttp.ClientSession() as session:
        backend = InfluxDB2Backend(session, ENV)
        await backend.validate()

        now = datetime.now(UTC).replace(microsecond=123456)
        attrs = {"unit_of_measurement": "°C", "friendly_name": 'Live "test"'}
        points = [
            state_to_point("sensor.live_temp", "21.5", attrs, now, SchemaOptions()),
            state_to_point(
                "binary_sensor.live_door",
                "on",
                {},
                now,
                SchemaOptions(),
                heartbeat=True,
            ),
        ]
        await backend.write(points)

        expected = {
            ("°C", "live_temp", "value", "21.5"),
            ("°C", "live_temp", "friendly_name_str", 'Live "test"'),
            ("binary_sensor.live_door", "live_door", "state", "on"),
            ("binary_sensor.live_door", "live_door", "value", "1"),
            ("binary_sensor.live_door", "live_door", "_heartbeat", "true"),
        }
        # A write is acknowledged (204) before the points can always be
        # queried, so wait for them a little (seen once in CI: empty result).
        for _ in range(QUERY_ATTEMPTS):
            rows = await _query(
                session,
                f'from(bucket: "{ENV["bucket"]}") |> range(start: -1h) '
                '|> filter(fn: (r) => r.entity_id == "live_temp" or r.entity_id == "live_door") '
                '|> keep(columns: ["_measurement", "domain", "entity_id", "_field", "_value"]) '
                "|> map(fn: (r) => ({r with _value: string(v: r._value)})) "
                "|> group()",
            )
            got = {
                (r["_measurement"], r["entity_id"], r["_field"], r["_value"])
                for r in rows
            }
            if expected <= got:
                break
            await asyncio.sleep(QUERY_DELAY)
        assert expected <= got, f"missing {expected - got}; rows: {rows}"
        assert all(r["domain"] in ("sensor", "binary_sensor") for r in rows)


async def test_validate_rejects_bad_token() -> None:
    """A wrong token is reported as an auth error."""
    async with aiohttp.ClientSession() as session:
        backend = InfluxDB2Backend(session, {**ENV, "token": "wrong"})
        with pytest.raises(BackendAuthError):
            await backend.validate()


async def test_validate_rejects_missing_bucket() -> None:
    """A bucket that does not exist is reported as not found."""
    async with aiohttp.ClientSession() as session:
        backend = InfluxDB2Backend(session, {**ENV, "bucket": "does-not-exist"})
        with pytest.raises(BackendNotFoundError):
            await backend.validate()
