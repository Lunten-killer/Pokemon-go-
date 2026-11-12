"""Datenabruf für Pokémon GO (Events, Raids, Eier, Forschung, News)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import html
import logging
import re
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXCLUDED_TYPES,
    CONF_LANGUAGE,
    CONF_SCAN_INTERVAL,
    DEFAULT_LANGUAGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_NEWS,
    NEWS_BASE,
    URL_EGGS,
    URL_EVENTS,
    URL_NEWS,
    URL_RAIDS,
    URL_RESEARCH,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=30)
HEADERS = {"User-Agent": "HomeAssistant-PokemonGO/1.0"}

_NEWS_CARD_RE = re.compile(
    r'<a\s[^>]*href="(?P<href>/[^"]*news/[^"#?]+)"[^>]*>(?P<body>.*?)</a>', re.S
)
_NEWS_TITLE_RE = re.compile(r'class="[^"]*newsCardTitle[^"]*"[^>]*>(.*?)</div>', re.S)
_NEWS_TS_RE = re.compile(r'timestamp="(\d+)"')
_NEWS_IMG_RE = re.compile(r'<img[^>]*\ssrc="([^"]+)"')
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class PokemonGoEvent:
    """Ein einzelnes Pokémon GO Event."""

    event_id: str
    name: str
    event_type: str
    heading: str
    link: str | None
    image: str | None
    start: datetime | None
    end: datetime | None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Kompakte Darstellung für Attribute."""
        return {
            "name": self.name,
            "type": self.event_type,
            "heading": self.heading,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "link": self.link,
            "image": self.image,
        }


@dataclass
class PokemonGoData:
    """Alle abgerufenen Daten."""

    events: list[PokemonGoEvent] = field(default_factory=list)
    raids: list[dict[str, Any]] = field(default_factory=list)
    eggs: list[dict[str, Any]] = field(default_factory=list)
    research: list[dict[str, Any]] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)

    def active_events(self, now: datetime) -> list[PokemonGoEvent]:
        """Events, die gerade laufen."""
        return [
            e
            for e in self.events
            if e.start and e.start <= now and (e.end is None or e.end > now)
        ]

    def upcoming_events(self, now: datetime) -> list[PokemonGoEvent]:
        """Zukünftige Events, nach Startzeit sortiert."""
        return sorted(
            (e for e in self.events if e.start and e.start > now),
            key=lambda e: e.start,  # type: ignore[arg-type, return-value]
        )


def parse_dt(value: str | None) -> datetime | None:
    """ISO-Zeit parsen. Ohne Zeitzone = lokale Zeit (z. B. Community Day 14-17 Uhr)."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


def parse_news(page: str, lang: str) -> list[dict[str, Any]]:
    """News-Karten aus der offiziellen News-Seite lesen."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _NEWS_CARD_RE.finditer(page):
        href = match.group("href")
        body = match.group("body")
        title_match = _NEWS_TITLE_RE.search(body)
        if not title_match or href in seen:
            continue
        seen.add(href)
        published = None
        if ts := _NEWS_TS_RE.search(body):
            published = dt_util.utc_from_timestamp(int(ts.group(1)) / 1000).isoformat()
        img = _NEWS_IMG_RE.search(body)
        items.append(
            {
                "title": _clean(title_match.group(1)),
                "link": f"{NEWS_BASE}{href}",
                "published": published,
                "image": html.unescape(img.group(1)) if img else None,
            }
        )
    return items


class PokemonGoCoordinator(DataUpdateCoordinator[PokemonGoData]):
    """Holt regelmäßig alle Pokémon GO Daten."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
        )
        self._session = async_get_clientsession(hass)
        self._known_news: set[str] | None = None

    @property
    def language(self) -> str:
        return self.config_entry.options.get(
            CONF_LANGUAGE, self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
        )

    @property
    def excluded_types(self) -> set[str]:
        return set(self.config_entry.options.get(CONF_EXCLUDED_TYPES, []))

    async def _get_json(self, url: str) -> Any:
        async with self._session.get(url, timeout=TIMEOUT, headers=HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _get_text(self, url: str) -> str:
        async with self._session.get(url, timeout=TIMEOUT, headers=HEADERS) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _async_update_data(self) -> PokemonGoData:
        previous = self.data or PokemonGoData()
        results = await asyncio.gather(
            self._get_json(URL_EVENTS),
            self._get_json(URL_RAIDS),
            self._get_json(URL_EGGS),
            self._get_json(URL_RESEARCH),
            self._get_text(URL_NEWS.format(lang=self.language)),
            return_exceptions=True,
        )
        raw_events, raids, eggs, research, news_page = results

        if isinstance(raw_events, BaseException):
            if not previous.events:
                raise UpdateFailed(f"Events konnten nicht geladen werden: {raw_events}")
            _LOGGER.warning("Events nicht abrufbar, nutze alte Daten: %s", raw_events)
            events = previous.events
        else:
            events = self._parse_events(raw_events)

        def keep(new: Any, old: list, what: str) -> list:
            if isinstance(new, BaseException) or not isinstance(new, list):
                _LOGGER.debug("%s nicht abrufbar, nutze alte Daten: %s", what, new)
                return old
            return new

        if isinstance(news_page, BaseException):
            _LOGGER.debug("News nicht abrufbar: %s", news_page)
            news = previous.news
        else:
            news = parse_news(news_page, self.language) or previous.news
            self._fire_new_news(news)

        return PokemonGoData(
            events=events,
            raids=keep(raids, previous.raids, "Raids"),
            eggs=keep(eggs, previous.eggs, "Eier"),
            research=keep(research, previous.research, "Forschung"),
            news=news,
        )

    def _parse_events(self, raw: list[dict[str, Any]]) -> list[PokemonGoEvent]:
        excluded = self.excluded_types
        events: list[PokemonGoEvent] = []
        for item in raw:
            event_type = item.get("eventType", "")
            if event_type in excluded:
                continue
            events.append(
                PokemonGoEvent(
                    event_id=item.get("eventID") or item.get("name", ""),
                    name=item.get("name", "Unbekanntes Event"),
                    event_type=event_type,
                    heading=item.get("heading", ""),
                    link=item.get("link"),
                    image=item.get("image"),
                    start=parse_dt(item.get("start")),
                    end=parse_dt(item.get("end")),
                    extra=item.get("extraData") or {},
                )
            )
        return events

    def _fire_new_news(self, news: list[dict[str, Any]]) -> None:
        links = {n["link"] for n in news}
        if self._known_news is not None:
            for item in news:
                if item["link"] not in self._known_news:
                    self.hass.bus.async_fire(EVENT_NEW_NEWS, item)
        self._known_news = links if self._known_news is None else self._known_news | links
