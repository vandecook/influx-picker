"""Overview of the selected entities, shown as text in the options flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant

from .selection import (
    Mode,
    Source,
    Status,
    compute_details,
    manual_lists,
    manual_status,
)

MAX_LINES = 100  # longer lists are shortened

# Placeholder values are not translated by Home Assistant, so the few words in
# the per-entity lines come from here (server language, English fallback).
_WORDS: dict[str, dict[Any, str]] = {
    "en": {
        Source.LABEL: "label",
        Source.DEVICE: "device",
        Source.AREA: "area",
        Source.MANUAL: "manual",
        Mode.CHANGE: "change",
        Mode.HEARTBEAT: "heartbeat",
        Status.MISSING: "missing",
        Status.DISABLED: "disabled",
        "none": "none",
        "more": "more",
    },
    "de": {
        Source.LABEL: "Label",
        Source.DEVICE: "Gerät",
        Source.AREA: "Bereich",
        Source.MANUAL: "manuell",
        Mode.CHANGE: "Änderung",
        Mode.HEARTBEAT: "Heartbeat",
        Status.MISSING: "fehlt",
        Status.DISABLED: "deaktiviert",
        "none": "keine",
        "more": "weitere",
    },
}
_SOURCE_ORDER = (Source.LABEL, Source.DEVICE, Source.AREA, Source.MANUAL)


def _words(hass: HomeAssistant) -> dict[Any, str]:
    language = (hass.config.language or "en").split("-")[0]
    return _WORDS.get(language, _WORDS["en"])


def build_overview(hass: HomeAssistant, options: Mapping[str, Any]) -> dict[str, str]:
    """Return the description placeholders of the overview step."""
    words = _words(hass)
    details = compute_details(hass, options)
    change, heartbeat = manual_lists(options)
    statuses = {e: manual_status(hass, e) for e in set(change) | set(heartbeat)}

    lines: list[str] = []
    for entity_id in sorted(details):
        sel = details[entity_id]
        sources = ", ".join(words[s] for s in _SOURCE_ORDER if s in sel.sources)
        line = f"- `{entity_id}`: {sources} · {words[sel.mode]}"
        if statuses.get(entity_id) is Status.MISSING:
            line += f" · **{words[Status.MISSING]}**"
        lines.append(line)
    # Disabled manual entries are not exported, but listed so they can be found.
    lines += [
        f"- `{e}`: {words[Source.MANUAL]} · **{words[Status.DISABLED]}**"
        for e in sorted(statuses)
        if statuses[e] is Status.DISABLED
    ]
    if len(lines) > MAX_LINES:
        rest = len(lines) - MAX_LINES
        lines = [*lines[:MAX_LINES], f"- … (+{rest} {words['more']})"]

    def count(source: Source) -> str:
        return str(sum(source in sel.sources for sel in details.values()))

    return {
        "total": str(len(details)),
        "change": str(sum(sel.mode is Mode.CHANGE for sel in details.values())),
        "heartbeat": str(sum(sel.mode is Mode.HEARTBEAT for sel in details.values())),
        "label": count(Source.LABEL),
        "device": count(Source.DEVICE),
        "area": count(Source.AREA),
        "manual": count(Source.MANUAL),
        "missing": str(sum(s is Status.MISSING for s in statuses.values())),
        "disabled": str(sum(s is Status.DISABLED for s in statuses.values())),
        "entities": "\n".join(lines) or f"- {words['none']}",
    }
