"""Runtime of one config entry: selection, state listener, heartbeat, exporter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
import time
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import (
    CoreState,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.state import state_as_number
from homeassistant.util import dt as dt_util

from .const import (
    CONF_HEARTBEAT_INTERVAL,
    CONF_STARTUP_SNAPSHOT,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_STARTUP_SNAPSHOT,
    STARTUP_SNAPSHOT_LAST_UPDATED,
    STARTUP_SNAPSHOT_OFF,
)
from .exporter import Exporter
from .issues import async_update_missing_issue
from .schema import SchemaOptions, state_to_point
from .selection import Mode, compute_selection, manual_lists, missing_manual

_LOGGER = logging.getLogger(__name__)

HEARTBEAT_CHECK_INTERVAL = timedelta(seconds=60)
REBUILD_COOLDOWN = 1.0  # seconds; registry events come in bursts

_REGISTRY_EVENTS = (
    er.EVENT_ENTITY_REGISTRY_UPDATED,
    dr.EVENT_DEVICE_REGISTRY_UPDATED,
    ar.EVENT_AREA_REGISTRY_UPDATED,
    lr.EVENT_LABEL_REGISTRY_UPDATED,
)


def _number(hass_state: State) -> Callable[[str], float]:
    """Use Home Assistant's own helper so on/off mapping stays in sync."""
    return lambda _state: float(state_as_number(hass_state))


class PickerRuntime:
    """Tracks the selected entities of one entry and feeds the exporter."""

    def __init__(
        self,
        hass: HomeAssistant,
        options: Mapping[str, Any],
        exporter: Exporter,
        schema_options: SchemaOptions | None = None,
        *,
        entry_id: str | None = None,
        title: str = "",
    ) -> None:
        """Store settings. Call `async_start()` to begin.

        With `entry_id`, a repairs issue lists manual entries that no longer
        exist (checked once Home Assistant has started).
        """
        self.hass = hass
        self.exporter = exporter
        self.schema_options = schema_options or SchemaOptions()
        self.options = dict(options)
        self.entry_id = entry_id
        self.title = title
        self._manual = set().union(*manual_lists(self.options))
        self.heartbeat_seconds: float = 60 * float(
            options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL)
        )
        self.startup_snapshot: str = (
            options.get(CONF_STARTUP_SNAPSHOT) or DEFAULT_STARTUP_SNAPSHOT
        )
        self._started = False
        self.tracked: dict[str, Mode] = {}
        self._last_write: dict[str, float] = {}  # entity_id -> self._clock()
        self._clock = time.monotonic  # replaced in tests
        self._unsubs: list[Callable[[], None]] = []
        self._debouncer: Debouncer | None = None

    @callback
    def async_start(self) -> None:
        """Build the selection and start listening."""
        self._debouncer = Debouncer(
            self.hass,
            _LOGGER,
            cooldown=REBUILD_COOLDOWN,
            immediate=False,
            function=self._async_rebuild,
        )
        self._unsubs.append(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                self._async_state_changed,
                event_filter=self._async_filter,
            )
        )
        for event_type in _REGISTRY_EVENTS:
            self._unsubs.append(
                self.hass.bus.async_listen(event_type, self._async_registry_changed)
            )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_heartbeat, HEARTBEAT_CHECK_INTERVAL
            )
        )
        self._async_rebuild()
        if self.entry_id is not None:
            # Entities without a unique ID appear only when their integration
            # has loaded, so check for missing ones after the start.
            self._unsubs.append(async_at_started(self.hass, self._async_at_started))

    @callback
    def _async_at_started(self, _hass: HomeAssistant) -> None:
        self._async_update_issue()

    @callback
    def _async_update_issue(self) -> None:
        # `is_running` is also true while starting, so check the state itself.
        if self.entry_id is None or self.hass.state is not CoreState.running:
            return
        async_update_missing_issue(
            self.hass,
            self.entry_id,
            self.title,
            missing_manual(self.hass, self.options),
        )

    @callback
    def async_stop(self) -> None:
        """Stop listening. The exporter is stopped by the caller."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._debouncer is not None:
            self._debouncer.async_cancel()

    @callback
    def _async_filter(self, event_data: EventStateChangedData) -> bool:
        return event_data["entity_id"] in self.tracked

    @callback
    def _async_registry_changed(self, _event: Event) -> None:
        if self._debouncer is not None:
            self._debouncer.async_schedule_call()

    @callback
    def _async_rebuild(self) -> None:
        """Recompute the selection. Newly selected entities get one snapshot.

        The first run after start follows the startup snapshot option.
        """
        new = compute_selection(self.hass, self.options)
        added = new.keys() - self.tracked.keys()
        removed = self.tracked.keys() - new.keys()
        self.tracked = new
        for entity_id in removed:
            self._last_write.pop(entity_id, None)
        startup, self._started = not self._started, True
        if startup and self.startup_snapshot == STARTUP_SNAPSHOT_OFF:
            # No write now; the first heartbeat comes after a full interval.
            started_at = self._clock()
            self._last_write.update(dict.fromkeys(added, started_at))
            added = set()
        now = dt_util.utcnow()
        for entity_id in added:
            if (state := self.hass.states.get(entity_id)) is None:
                continue
            if startup and self.startup_snapshot == STARTUP_SNAPSHOT_LAST_UPDATED:
                # Same timestamp as the change point the state came from, so an
                # existing point is overwritten with the same values (plus the
                # marker) and a missing one is filled in at the right time.
                self._write(state, state.last_updated, heartbeat=False, startup=True)
            else:
                self._write(state, now, heartbeat=True)
        if added or removed:
            _LOGGER.debug(
                "Selection: %d entities (+%d, -%d)", len(new), len(added), len(removed)
            )
        self._async_update_issue()

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        if (state := event.data["new_state"]) is not None:
            self._write(state, event.time_fired, heartbeat=False)
        if (
            event.data["entity_id"] in self._manual
            and (state is None or event.data["old_state"] is None)
            and self._debouncer is not None
        ):
            # A manual entry appeared or was removed: update the issue.
            self._debouncer.async_schedule_call()

    @callback
    def _async_heartbeat(self, _now: datetime) -> None:
        threshold = self._clock() - self.heartbeat_seconds
        now = dt_util.utcnow()
        for entity_id, mode in self.tracked.items():
            if mode is not Mode.HEARTBEAT:
                continue
            last = self._last_write.get(entity_id)
            if last is not None and last > threshold:
                continue
            if (state := self.hass.states.get(entity_id)) is not None:
                self._write(state, now, heartbeat=True)

    @callback
    def _write(
        self,
        state: State,
        when: datetime,
        *,
        heartbeat: bool,
        startup: bool = False,
    ) -> None:
        point = state_to_point(
            state.entity_id,
            state.state,
            state.attributes,
            when,
            self.schema_options,
            heartbeat=heartbeat,
            startup=startup,
            number=_number(state),
        )
        if point is not None:
            self.exporter.add(point)
            self._last_write[state.entity_id] = self._clock()
