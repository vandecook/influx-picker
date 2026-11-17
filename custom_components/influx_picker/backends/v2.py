"""Backend for InfluxDB 2.x (HTTP API `/api/v2/write`, line protocol)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import aiohttp
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from yarl import URL

from .. import line_protocol
from .._vol import vol
from ..const import (
    CONF_BUCKET,
    CONF_ORG,
    CONF_PRECISION,
    CONF_TOKEN,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_PRECISION,
    WRITE_TIMEOUT,
)
from ..point import Point
from .base import (
    Backend,
    BackendAuthError,
    BackendConnectionError,
    BackendInvalidDataError,
    BackendNotFoundError,
    register,
)

_INVALID_DATA = {400, 413, 422}
_AUTH = {401, 403}


@register
class InfluxDB2Backend(Backend):
    """Write to InfluxDB 2.x with a token, an organization and a bucket."""

    version = "v2"

    @staticmethod
    def schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
        """Fields: URL, organization, bucket, token, certificate check."""
        d = defaults or {}
        text = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
        return vol.Schema(
            {
                vol.Required(
                    CONF_URL, default=d.get(CONF_URL, "http://localhost:8086")
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_ORG, default=d.get(CONF_ORG, vol.UNDEFINED)): text,
                vol.Required(
                    CONF_BUCKET, default=d.get(CONF_BUCKET, vol.UNDEFINED)
                ): text,
                vol.Required(CONF_TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_VERIFY_SSL, default=d.get(CONF_VERIFY_SSL, True)
                ): bool,
            }
        )

    @staticmethod
    def title(config: Mapping[str, Any]) -> str:
        """Bucket name and server, for example "ha (localhost:8086)"."""
        url = URL(str(config[CONF_URL]))
        host = url.host or str(config[CONF_URL])
        if url.explicit_port:
            host = f"{host}:{url.explicit_port}"
        return f"{config[CONF_BUCKET]} ({host})"

    @staticmethod
    def unique_id(config: Mapping[str, Any]) -> str | None:
        """One entry per URL, organization and bucket."""
        url = str(config[CONF_URL]).rstrip("/")
        return f"v2|{url}|{config[CONF_ORG]}|{config[CONF_BUCKET]}"

    @property
    def _write_url(self) -> str:
        return str(self._config[CONF_URL]).rstrip("/") + "/api/v2/write"

    @property
    def _precision(self) -> str:
        return self._config.get(CONF_PRECISION, DEFAULT_PRECISION)

    async def _post(self, body: str) -> None:
        params = {
            "org": self._config[CONF_ORG],
            "bucket": self._config[CONF_BUCKET],
            "precision": self._precision,
        }
        headers = {
            "Authorization": f"Token {self._config[CONF_TOKEN]}",
            "Content-Type": "text/plain; charset=utf-8",
        }
        try:
            async with self._session.post(
                self._write_url,
                params=params,
                data=body.encode("utf-8"),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=WRITE_TIMEOUT),
            ) as resp:
                if resp.status == 204:
                    return
                text = (await resp.text())[:300]
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BackendConnectionError(f"Cannot reach InfluxDB: {err!r}") from err

        message = f"HTTP {status}: {text}"
        if status in _INVALID_DATA:
            raise BackendInvalidDataError(message)
        if status in _AUTH:
            raise BackendAuthError(message)
        if status == 404:
            raise BackendNotFoundError(message)
        raise BackendConnectionError(message)

    async def validate(self) -> None:
        """Send an empty write.

        The server checks token, organization and bucket before it parses the
        body, so 204 or 400 (empty body) means the target is writable. The core
        integration uses the same check.
        """
        try:
            await self._post("")
        except BackendInvalidDataError:
            return

    async def write(self, points: Sequence[Point]) -> None:
        """Write points as one request."""
        body = line_protocol.to_body(points, self._precision)
        if body:
            await self._post(body)
