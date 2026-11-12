"""Kalender mit allen Pokémon GO Events."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PokemonGoConfigEntry
from .coordinator import PokemonGoEvent
from .entity import PokemonGoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PokemonGoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PokemonGoCalendar(entry.runtime_data, "calendar")])


def _to_calendar_event(event: PokemonGoEvent) -> CalendarEvent | None:
    if event.start is None:
        return None
    end = event.end or event.start + timedelta(hours=1)
    if end <= event.start:
        end = event.start + timedelta(minutes=1)
    description = "\n".join(
        part for part in (event.heading, event.link) if part
    )
    return CalendarEvent(
        start=event.start,
        end=end,
        summary=event.name,
        description=description or None,
        uid=event.event_id,
        location=event.heading or None,
    )


class PokemonGoCalendar(PokemonGoEntity, CalendarEntity):
    """Kalender-Entität."""

    _attr_translation_key = "events"
    _attr_icon = "mdi:pokeball"

    @property
    def event(self) -> CalendarEvent | None:
        """Aktuelles bzw. nächstes Event."""
        now = dt_util.now()
        candidates = sorted(
            (e for e in self.coordinator.data.events if e.start and (e.end or e.start) > now),
            key=lambda e: e.start,  # type: ignore[arg-type, return-value]
        )
        for event in candidates:
            if cal := _to_calendar_event(event):
                return cal
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        result: list[CalendarEvent] = []
        for event in self.coordinator.data.events:
            cal = _to_calendar_event(event)
            if cal and cal.start_datetime_local < end_date and cal.end_datetime_local > start_date:
                result.append(cal)
        return sorted(result, key=lambda c: c.start_datetime_local)
