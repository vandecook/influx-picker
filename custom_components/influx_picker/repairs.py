"""Repairs fix flow: remove manually listed entities that no longer exist."""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .issues import format_entities
from .selection import missing_manual, without_entities


class RemoveMissingFlow(RepairsFlow):
    """Confirm, then drop the missing entries from the entry's manual lists."""

    def __init__(self, entry_id: str) -> None:
        """Remember which entry the issue belongs to."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start with the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the missing entities; remove them on submit."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_removed")
        missing = missing_manual(self.hass, entry.options)
        if user_input is not None:
            if missing:
                # Saving the options reloads the entry, which clears the issue.
                self.hass.config_entries.async_update_entry(
                    entry, options=without_entities(entry.options, missing)
                )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "title": entry.title,
                "entities": format_entities(missing) or "-",
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the fix flow for an issue of this integration."""
    return RemoveMissingFlow(str((data or {}).get("entry_id", "")))
