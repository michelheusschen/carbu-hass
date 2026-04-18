"""DataUpdateCoordinator for the Carbu Fuel Prices integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CarbuApiClient, CarbuApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, FuelType
from .models import FuelPrediction, FuelStation

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class CarbuFuelCoordinator(DataUpdateCoordinator[dict[str, FuelStation]]):
    """Coordinator to fetch fuel prices for one location and fuel type.

    Data is stored as a dict mapping station_id -> FuelStation.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: CarbuApiClient,
        town: str,
        postal_code: str,
        location_id: str,
        fuel_type: FuelType,
        entry_title: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.api_client = api_client
        self.town = town
        self.postal_code = postal_code
        self.location_id = location_id
        self.fuel_type = fuel_type
        self.entry_title = entry_title or f"{town} {postal_code} - {fuel_type.label}"
        self.prediction: FuelPrediction | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{postal_code}_{fuel_type.code}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, FuelStation]:
        """Fetch fuel station data from carbu.com."""
        try:
            stations = await self.api_client.get_fuel_stations(
                town=self.town,
                postal_code=self.postal_code,
                location_id=self.location_id,
                fuel_type=self.fuel_type,
            )
        except CarbuApiError as err:
            raise UpdateFailed(
                f"Error fetching {self.fuel_type.label} prices for {self.postal_code}: {err}"
            ) from err

        self.prediction = None
        if self.fuel_type.prediction_code is not None:
            try:
                self.prediction = await self.api_client.get_fuel_prediction(self.fuel_type)
            except CarbuApiError as err:
                _LOGGER.debug(
                    "Prediction unavailable for %s at %s: %s",
                    self.fuel_type.label,
                    self.postal_code,
                    err,
                )

        _LOGGER.debug(
            "Fetched %d stations for %s at %s",
            len(stations),
            self.fuel_type.label,
            self.postal_code,
        )

        return {station.station_id: station for station in stations}
