"""The Carbu Fuel Prices integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CarbuApiClient
from .const import (
    CONF_FUEL_TYPE,
    CONF_LOCATION_ID,
    CONF_POSTAL_CODE,
    CONF_TOWN,
    FuelType,
)
from .coordinator import CarbuFuelCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Carbu Fuel Prices from a config entry."""
    session = async_get_clientsession(hass)
    api_client = CarbuApiClient(session)

    fuel_type = FuelType.from_code(entry.data[CONF_FUEL_TYPE])

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=api_client,
        town=entry.data[CONF_TOWN],
        postal_code=entry.data[CONF_POSTAL_CODE],
        location_id=entry.data[CONF_LOCATION_ID],
        fuel_type=fuel_type,
        entry_title=entry.title,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
