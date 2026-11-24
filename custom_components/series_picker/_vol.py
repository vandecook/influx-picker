"""Schema library used by Home Assistant.

Recent Home Assistant versions use `probatio`, older ones `voluptuous`.
"""

try:
    import probatio as vol
except ImportError:  # pragma: no cover - depends on the Home Assistant version
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
