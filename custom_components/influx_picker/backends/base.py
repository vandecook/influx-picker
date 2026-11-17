"""Backend interface and registry.

A backend knows how to talk to one InfluxDB major version. Adding a version is
one module with a `Backend` subclass decorated with `@register`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import aiohttp

from ..point import Point


class BackendError(Exception):
    """Base class for backend errors."""


class BackendConnectionError(BackendError):
    """Temporary problem (network, server error, timeout). The batch is retried."""


class BackendAuthError(BackendError):
    """Credentials are wrong or lack permission. Retried, but needs the user."""


class BackendInvalidDataError(BackendError):
    """The server rejected the data (HTTP 400/413/422). The batch is dropped."""


class BackendNotFoundError(BackendError):
    """The target (bucket, database, org) does not exist."""


class Backend(ABC):
    """Interface every backend implements."""

    #: Registry key, for example "v2". Stored in the config entry.
    version: ClassVar[str]

    def __init__(self, session: aiohttp.ClientSession, config: Mapping[str, Any]):
        """Store the HTTP session and the backend part of the entry data."""
        self._session = session
        self._config = dict(config)

    @staticmethod
    @abstractmethod
    def schema(defaults: Mapping[str, Any] | None = None) -> Any:
        """Return the config flow schema for the backend-specific fields."""

    @staticmethod
    @abstractmethod
    def title(config: Mapping[str, Any]) -> str:
        """Return a default title for the config entry."""

    @staticmethod
    def unique_id(config: Mapping[str, Any]) -> str | None:
        """Return an ID for the target, used to stop duplicate entries. None: no check."""
        return None

    @abstractmethod
    async def validate(self) -> None:
        """Check the connection for real (credentials and target). Raise BackendError."""

    @abstractmethod
    async def write(self, points: Sequence[Point]) -> None:
        """Write points. Raise a BackendError subclass on failure."""

    async def close(self) -> None:  # noqa: B027
        """Release resources. The shared HTTP session is not closed here."""


BACKENDS: dict[str, type[Backend]] = {}


def register(cls: type[Backend]) -> type[Backend]:
    """Class decorator that adds a backend to the registry."""
    if cls.version in BACKENDS:
        raise ValueError(f"Backend {cls.version!r} is already registered")
    BACKENDS[cls.version] = cls
    return cls


def get_backend(version: str) -> type[Backend]:
    """Return the backend class for a version key. Raises KeyError."""
    return BACKENDS[version]
