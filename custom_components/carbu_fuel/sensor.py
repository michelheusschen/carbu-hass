"""Sensor entities for the Carbu Fuel Prices integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CarbuFuelCoordinator
from .models import FuelStation

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


def _prediction_unique_id(coordinator: CarbuFuelCoordinator) -> str:
    """Return unique_id for the per-entry prediction sensor."""
    return f"{DOMAIN}_{coordinator.postal_code}_{coordinator.fuel_type.code}_prediction"


def _lowest_price_unique_id(coordinator: CarbuFuelCoordinator) -> str:
    """Return unique_id for the per-entry lowest-price sensor."""
    return f"{DOMAIN}_{coordinator.location_id}_{coordinator.fuel_type.code}_lowest_price"


def _device_station_id(device_entry: dr.DeviceEntry) -> str | None:
    """Return the station identifier stored in a carbu device identifier."""
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN:
            return identifier

    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    coordinator: CarbuFuelCoordinator = entry.runtime_data

    async_add_entities([CarbuFuelLowestPriceSensor(coordinator)])

    if coordinator.fuel_type.prediction_code is not None:
        async_add_entities([CarbuFuelPredictionSensor(coordinator)])

    # Track which station IDs we've already created entities for
    known_station_ids: set[str] = set()

    def _add_new_entities() -> None:
        """Add entities for any new stations found by the coordinator."""
        if coordinator.data is None:
            return

        current_station_ids = set(coordinator.data)
        expected_unique_ids = {
            f"{DOMAIN}_{station_id}_{coordinator.fuel_type.code}"
            for station_id in current_station_ids
        }
        expected_unique_ids.add(_lowest_price_unique_id(coordinator))
        if coordinator.fuel_type.prediction_code is not None:
            expected_unique_ids.add(_prediction_unique_id(coordinator))

        # Remove entities that no longer exist in the parsed station list.
        entity_registry = er.async_get(hass)
        unique_id_prefix = f"{DOMAIN}_"

        removed_count = 0
        for registry_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            unique_id = registry_entry.unique_id
            if not unique_id.startswith(unique_id_prefix):
                continue

            if unique_id not in expected_unique_ids:
                entity_registry.async_remove(registry_entry.entity_id)
                # Also forget this station ID from our in-memory set when the
                # unique_id follows the current DOMAIN_station_fuel format.
                station_id = unique_id.removeprefix(unique_id_prefix).rsplit("_", 1)[0]
                if station_id:
                    known_station_ids.discard(station_id)
                removed_count += 1

        if removed_count:
            _LOGGER.debug(
                "Removed %d stale fuel station entities for %s",
                removed_count,
                coordinator.fuel_type.label,
            )

        # Remove stale station devices that no longer have any entities.
        device_registry = dr.async_get(hass)
        removed_device_count = 0
        for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            station_id = _device_station_id(device_entry)
            if station_id is None or station_id.startswith("prediction_"):
                continue

            if station_id in current_station_ids:
                continue

            if er.async_entries_for_device(entity_registry, device_entry.id):
                continue

            device_registry.async_remove_device(device_entry.id)
            removed_device_count += 1

        if removed_device_count:
            _LOGGER.debug(
                "Removed %d stale fuel station devices for %s",
                removed_device_count,
                coordinator.fuel_type.label,
            )

        new_entities: list[CarbuFuelStationSensor] = []
        for station_id in current_station_ids:
            if station_id not in known_station_ids:
                known_station_ids.add(station_id)
                new_entities.append(CarbuFuelStationSensor(coordinator, station_id))

        if new_entities:
            _LOGGER.debug(
                "Adding %d new fuel station entities for %s",
                len(new_entities),
                coordinator.fuel_type.label,
            )
            async_add_entities(new_entities)

    # Add entities for the initial data
    _add_new_entities()

    # Listen for future updates to add new stations dynamically
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class CarbuFuelStationSensor(CoordinatorEntity[CarbuFuelCoordinator], SensorEntity):
    """Sensor entity representing a fuel station's price.

    State: the fuel price (e.g. 1.609 €/L).
    Attributes: station details (name, brand, address, distance, etc.).
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gas-station"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CarbuFuelCoordinator,
        station_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station_id = station_id

        # Set unit based on country
        self._attr_native_unit_of_measurement = "€/L"
        self._attr_suggested_display_precision = 3

        # Set unique_id
        self._attr_unique_id = f"{DOMAIN}_{station_id}_{coordinator.fuel_type.code}"

        # Set entity name to the fuel type
        self._attr_name = coordinator.fuel_type.label

    @property
    def _station(self) -> FuelStation | None:
        """Get the current station data from the coordinator."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._station_id)

    @property
    def available(self) -> bool:
        """Return True if station data is available."""
        return super().available and self._station is not None

    @property
    def native_value(self) -> float | None:
        """Return the fuel price."""
        station = self._station
        return station.price if station else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return station details as extra state attributes."""
        station = self._station
        if station is None:
            return {}

        return {
            "station_name": station.name,
            "brand": station.brand,
            "fuel_name": station.fuel_name,
            "address": station.address,
            "postal_code": station.postal_code,
            "city": station.city,
            "distance_km": station.distance_km,
            "date": station.date,
            "url": station.url,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "station_id": station.station_id,
            "country": station.country,
        }

    @property
    def entity_picture(self) -> str | None:
        """Return the station logo URL."""
        station = self._station
        return station.logo_url if station else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to group entities by station.

        All fuel types for the same physical station are grouped
        under one device.
        """
        station = self._station
        if station is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self._station_id)},
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._station_id)},
            name=station.name,
            manufacturer=station.brand,
            model="Fuel Station",
            configuration_url=station.url,
        )


class CarbuFuelLowestPriceSensor(CoordinatorEntity[CarbuFuelCoordinator], SensorEntity):
    """Sensor entity representing the lowest available station price for an entry."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash-check"
    _attr_native_unit_of_measurement = "€/L"
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: CarbuFuelCoordinator) -> None:
        """Initialize the lowest-price sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = _lowest_price_unique_id(coordinator)
        self._attr_name = f"{coordinator.postal_code} {coordinator.fuel_type.label} lowest price"

    @property
    def _lowest_station(self) -> FuelStation | None:
        """Return the station with the lowest current price."""
        if not self.coordinator.data:
            return None
        return min(self.coordinator.data.values(), key=lambda station: station.price)

    @property
    def available(self) -> bool:
        """Return True if at least one station is available."""
        return super().available and self._lowest_station is not None

    @property
    def native_value(self) -> float | None:
        """Return the lowest station price."""
        station = self._lowest_station
        return station.price if station else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details for the station currently offering the lowest price."""
        station = self._lowest_station
        if station is None:
            return {}

        return {
            "station_name": station.name,
            "station_id": station.station_id,
            "brand": station.brand,
            "fuel_name": station.fuel_name,
            "address": station.address,
            "postal_code": station.postal_code,
            "city": station.city,
            "distance_km": station.distance_km,
            "date": station.date,
            "url": station.url,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "country": station.country,
            "location_id": self.coordinator.location_id,
            "town": self.coordinator.town,
            "entry_postal_code": self.coordinator.postal_code,
            "entry_title": self.coordinator.entry_title,
        }


class CarbuFuelPredictionSensor(CoordinatorEntity[CarbuFuelCoordinator], SensorEntity):
    """Sensor entity representing upcoming market-level fuel trend prediction."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:chart-line"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 3

    def __init__(self, coordinator: CarbuFuelCoordinator) -> None:
        """Initialize the prediction sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = _prediction_unique_id(coordinator)
        self._attr_name = f"{coordinator.fuel_type.label} prediction"

    @property
    def available(self) -> bool:
        """Return True if prediction data is available."""
        return super().available and self.coordinator.prediction is not None

    @property
    def native_value(self) -> float | None:
        """Return the prediction trend percentage."""
        prediction = self.coordinator.prediction
        return prediction.trend_percent if prediction else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return prediction metadata."""
        prediction = self.coordinator.prediction
        if prediction is None:
            return {}

        return {
            "baseline_date": prediction.baseline_date,
            "forecast_date": prediction.forecast_date,
            "baseline_price": prediction.baseline_price,
            "predicted_price": prediction.predicted_price,
            "method": "carbu max-price forecast page (+5 workday trend)",
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the prediction sensor."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"prediction_{self.coordinator.postal_code}_{self.coordinator.fuel_type.code}",
                )
            },
            name=f"{self.coordinator.postal_code} {self.coordinator.fuel_type.label}",
            model="Fuel Price Prediction",
            manufacturer="carbu.com",
        )
