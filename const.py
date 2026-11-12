"""Konstanten für die Pokémon GO Integration."""

from __future__ import annotations

DOMAIN = "pokemon_go"

CONF_LANGUAGE = "language"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_EXCLUDED_TYPES = "excluded_types"

DEFAULT_LANGUAGE = "de"
DEFAULT_SCAN_INTERVAL = 30  # Minuten
MIN_SCAN_INTERVAL = 10

# Datenquellen
# ScrapedDuck spiegelt die Daten von leekduck.com als JSON (stündlich aktualisiert).
SCRAPEDDUCK_BASE = "https://raw.githubusercontent.com/bigfoott/ScrapedDuck/data"
URL_EVENTS = f"{SCRAPEDDUCK_BASE}/events.min.json"
URL_RAIDS = f"{SCRAPEDDUCK_BASE}/raids.min.json"
URL_EGGS = f"{SCRAPEDDUCK_BASE}/eggs.min.json"
URL_RESEARCH = f"{SCRAPEDDUCK_BASE}/research.min.json"
# Offizielle Pokémon GO News (Sprache wird eingesetzt)
URL_NEWS = "https://pokemongolive.com/{lang}/news"
NEWS_BASE = "https://pokemongolive.com"

# Feuert, wenn neue offizielle News erscheinen
EVENT_NEW_NEWS = "pokemon_go_new_news"

NEWS_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "it": "Italiano",
    "es": "Español",
    "pl": "Polski",
    "pt-BR": "Português (Brasil)",
    "tr": "Türkçe",
    "ja": "日本語",
    "ko": "한국어",
}

# Bekannte Event-Typen von LeekDuck (für den Filter in den Optionen)
EVENT_TYPES = [
    "community-day",
    "pokemon-spotlight-hour",
    "raid-hour",
    "raid-day",
    "raid-battles",
    "raid-weekend",
    "elite-raids",
    "max-battles",
    "max-mondays",
    "go-battle-league",
    "event",
    "live-event",
    "pokemon-go-fest",
    "pokemon-go-tour",
    "wild-area",
    "city-safari",
    "safari-zone",
    "global-challenge",
    "ticketed-event",
    "go-pass",
    "location-specific",
    "bonus-hour",
    "pokestop-showcase",
    "research",
    "timed-research",
    "limited-research",
    "special-research",
    "research-breakthrough",
    "research-day",
    "season",
    "update",
    "potential-ultra-unlock",
]
