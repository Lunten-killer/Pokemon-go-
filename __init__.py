"""Pokémon GO Integration für Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import PokemonGoCoordinator

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]

type PokemonGoConfigEntry = ConfigEntry[PokemonGoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PokemonGoConfigEntry) -> bool:
    """Integration einrichten."""
    coordinator = PokemonGoCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PokemonGoConfigEntry) -> bool:
    """Integration entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: PokemonGoConfigEntry) -> None:
    """Bei geänderten Optionen neu laden."""
    await hass.config_entries.async_reload(entry.entry_id)
