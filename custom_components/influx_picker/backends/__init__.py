"""Backends. Importing this package registers all built-in backends."""

from . import v2  # noqa: F401  (registers the backend)
from .base import (
    BACKENDS,
    Backend,
    BackendAuthError,
    BackendConnectionError,
    BackendError,
    BackendInvalidDataError,
    BackendNotFoundError,
    get_backend,
    register,
)

__all__ = [
    "BACKENDS",
    "Backend",
    "BackendAuthError",
    "BackendConnectionError",
    "BackendError",
    "BackendInvalidDataError",
    "BackendNotFoundError",
    "get_backend",
    "register",
]
