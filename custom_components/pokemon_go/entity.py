"""Basisklasse für Pokémon GO Entitäten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PokemonGoCoordinator


class PokemonGoEntity(CoordinatorEntity[PokemonGoCoordinator]):
    """Gemeinsame Geräteinfos."""

    _attr_has_entity_name = True
    _attr_attribution = "Daten: LeekDuck (via ScrapedDuck) & pokemongolive.com"

    def __init__(self, coordinator: PokemonGoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name="Pokémon GO",
            manufacturer="Niantic (inoffiziell)",
            model="Events & News",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://leekduck.com/events/",
        )
