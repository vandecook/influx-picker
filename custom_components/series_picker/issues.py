"""Repairs issue for manually listed entities that no longer exist."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

ISSUE_MISSING_MANUAL = "missing_manual_entities"


def issue_id(entry_id: str) -> str:
    """One issue per config entry."""
    return f"{ISSUE_MISSING_MANUAL}_{entry_id}"


def format_entities(entity_ids: Sequence[str], limit: int = 20) -> str:
    """Markdown list, shortened for long lists."""
    lines = [f"- `{e}`" for e in entity_ids[:limit]]
    if len(entity_ids) > limit:
        lines.append(f"- … (+{len(entity_ids) - limit})")
    return "\n".join(lines)


@callback
def async_update_missing_issue(
    hass: HomeAssistant, entry_id: str, title: str, missing: Sequence[str]
) -> None:
    """Create, update or delete the issue for one entry."""
    if not missing:
        ir.async_delete_issue(hass, DOMAIN, issue_id(entry_id))
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id(entry_id),
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_MISSING_MANUAL,
        translation_placeholders={
            "title": title,
            "count": str(len(missing)),
            "entities": format_entities(missing),
        },
        data={"entry_id": entry_id},
    )


@callback
def async_delete_missing_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Remove the issue of a removed entry."""
    ir.async_delete_issue(hass, DOMAIN, issue_id(entry_id))
