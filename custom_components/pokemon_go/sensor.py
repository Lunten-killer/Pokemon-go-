"""Sensoren für Pokémon GO."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import PokemonGoConfigEntry
from .coordinator import PokemonGoData, PokemonGoEvent
from .entity import PokemonGoEntity

_TAG_RE = re.compile(r"<[^>]+>")
MAX_LIST = 25


def _next_of_type(data: PokemonGoData, now: datetime, *types: str) -> PokemonGoEvent | None:
    """Laufendes oder nächstes Event eines Typs."""
    events = sorted(
        (
            e
            for e in data.events
            if e.event_type in types and e.start and (e.end or e.start) > now
        ),
        key=lambda e: e.start,  # type: ignore[arg-type, return-value]
    )
    return events[0] if events else None


def _event_attrs(event: PokemonGoEvent | None, now: datetime) -> dict[str, Any]:
    if event is None:
        return {}
    attrs = event.as_dict()
    attrs["active"] = bool(event.start and event.start <= now)
    if event.start:
        attrs["days_until"] = max(0, (event.start.date() - now.date()).days)
    return attrs


def _group(items: list[dict[str, Any]], key: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in items:
        name = item.get("name", "?") + (" ✨" if item.get("canBeShiny") else "")
        grouped.setdefault(item.get(key) or "Andere", []).append(name)
    return grouped


def _raid_details(raids: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": r.get("name"),
            "tier": r.get("tier"),
            "shiny": r.get("canBeShiny", False),
            "types": [t.get("name") for t in r.get("types", [])],
            "cp": (r.get("combatPower") or {}).get("normal"),
            "cp_boosted": (r.get("combatPower") or {}).get("boosted"),
            "weather": [w.get("name") for w in r.get("boostedWeather", [])],
            "image": r.get("image"),
        }
        for r in raids
    ]


def _research_tasks(research: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "task": _TAG_RE.sub("", t.get("text", "")).strip(),
            "rewards": [
                rw.get("name", "?") + (" ✨" if rw.get("canBeShiny") else "")
                for rw in t.get("rewards", [])
            ],
        }
        for t in research
    ]


@dataclass(frozen=True, kw_only=True)
class PokemonGoSensorDescription(SensorEntityDescription):
    """Beschreibung eines Sensors."""

    value_fn: Callable[[PokemonGoData, datetime], Any]
    attr_fn: Callable[[PokemonGoData, datetime], dict[str, Any]] = lambda d, n: {}


def _next_type_sensor(key: str, icon: str, *types: str) -> PokemonGoSensorDescription:
    return PokemonGoSensorDescription(
        key=key,
        translation_key=key,
        icon=icon,
        value_fn=lambda d, n: (ev.name[:255] if (ev := _next_of_type(d, n, *types)) else None),
        attr_fn=lambda d, n: _event_attrs(_next_of_type(d, n, *types), n),
    )


def _next_event(d: PokemonGoData, n: datetime) -> PokemonGoEvent | None:
    upcoming = d.upcoming_events(n)
    return upcoming[0] if upcoming else None


SENSORS: tuple[PokemonGoSensorDescription, ...] = (
    PokemonGoSensorDescription(
        key="active_events",
        translation_key="active_events",
        icon="mdi:calendar-star",
        native_unit_of_measurement="Events",
        value_fn=lambda d, n: len(d.active_events(n)),
        attr_fn=lambda d, n: {
            "events": [e.as_dict() for e in d.active_events(n)][:MAX_LIST]
        },
    ),
    PokemonGoSensorDescription(
        key="next_event",
        translation_key="next_event",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d, n: (ev.start if (ev := _next_event(d, n)) else None),
        attr_fn=lambda d, n: {
            **_event_attrs(_next_event(d, n), n),
            "upcoming": [e.as_dict() for e in d.upcoming_events(n)][:MAX_LIST],
        },
    ),
    _next_type_sensor("next_community_day", "mdi:account-group", "community-day"),
    _next_type_sensor("next_spotlight_hour", "mdi:spotlight-beam", "pokemon-spotlight-hour"),
    _next_type_sensor("next_raid_hour", "mdi:sword-cross", "raid-hour"),
    _next_type_sensor("next_raid_day", "mdi:shield-sword", "raid-day", "raid-weekend", "elite-raids"),
    _next_type_sensor("next_max_battle", "mdi:star-four-points", "max-mondays", "max-battles"),
    _next_type_sensor(
        "next_big_event",
        "mdi:party-popper",
        "pokemon-go-fest",
        "pokemon-go-tour",
        "wild-area",
        "live-event",
        "city-safari",
        "safari-zone",
    ),
    PokemonGoSensorDescription(
        key="raid_bosses",
        translation_key="raid_bosses",
        icon="mdi:sword",
        native_unit_of_measurement="Bosse",
        value_fn=lambda d, n: len(d.raids),
        attr_fn=lambda d, n: {
            "by_tier": _group(d.raids, "tier"),
            "bosses": _raid_details(d.raids),
        },
    ),
    PokemonGoSensorDescription(
        key="eggs",
        translation_key="eggs",
        icon="mdi:egg",
        native_unit_of_measurement="Pokémon",
        value_fn=lambda d, n: len(d.eggs),
        attr_fn=lambda d, n: {"by_egg": _group(d.eggs, "eggType")},
    ),
    PokemonGoSensorDescription(
        key="field_research",
        translation_key="field_research",
        icon="mdi:clipboard-search",
        native_unit_of_measurement="Aufgaben",
        value_fn=lambda d, n: len(d.research),
        attr_fn=lambda d, n: {"tasks": _research_tasks(d.research)},
    ),
    PokemonGoSensorDescription(
        key="latest_news",
        translation_key="latest_news",
        icon="mdi:newspaper",
        value_fn=lambda d, n: d.news[0]["title"][:255] if d.news else None,
        attr_fn=lambda d, n: {
            **(d.news[0] if d.news else {}),
            "news": d.news[:15],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PokemonGoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PokemonGoSensor(coordinator, desc) for desc in SENSORS)


class PokemonGoSensor(PokemonGoEntity, SensorEntity):
    """Ein Pokémon GO Sensor."""

    entity_description: PokemonGoSensorDescription

    def __init__(self, coordinator, description: PokemonGoSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data, dt_util.now())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.entity_description.attr_fn(self.coordinator.data, dt_util.now())
