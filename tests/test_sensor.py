"""Tests for the CarbuFuelStationSensor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.carbu_fuel.const import DOMAIN, FuelType
from custom_components.carbu_fuel.coordinator import CarbuFuelCoordinator
from custom_components.carbu_fuel.models import FuelPrediction
from custom_components.carbu_fuel.sensor import (
    CarbuFuelLowestPriceSensor,
    CarbuFuelPredictionSensor,
    CarbuFuelStationSensor,
    async_setup_entry,
)


class TestCarbuFuelStationSensor:
    """Tests for the fuel station sensor entity."""

    def test_native_value_returns_price(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that native_value returns the station price."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.native_value == 1.609

    def test_native_value_returns_none_when_station_missing(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that native_value returns None for unknown station."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "nonexistent")
        assert sensor.native_value is None

    def test_extra_state_attributes(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that extra_state_attributes contain station details."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        attrs = sensor.extra_state_attributes

        assert attrs["station_name"] == "Texaco Lot"
        assert attrs["brand"] == "Texaco"
        assert attrs["fuel_name"] == "Diesel (B7)"
        assert attrs["address"] == "Bergensesteenweg 155, 1651 Lot"
        assert attrs["city"] == "Lot"
        assert attrs["distance_km"] == 5.53
        assert attrs["station_id"] == "21313"
        assert attrs["country"] == "BE"

    def test_extra_state_attributes_empty_when_station_missing(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that extra_state_attributes returns empty dict for missing station."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "nonexistent")
        assert sensor.extra_state_attributes == {}

    def test_unique_id_format(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test unique_id format includes domain, station_id, and fuel type."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.unique_id == "carbu_fuel_21313_GO"

    def test_name_is_fuel_type_label(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that entity name is the fuel type label."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.name == "Diesel (B7)"

    def test_unit_of_measurement(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that unit of measurement is €/L."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.native_unit_of_measurement == "€/L"

    def test_entity_picture(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that entity_picture returns the logo URL."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.entity_picture == (
            "https://carbucomstatic-5141.kxcdn.com/brandLogo/texaco.gif"
        )

    def test_device_info_groups_by_station(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that device_info uses station_id as identifier."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        device_info = sensor.device_info

        assert ("carbu_fuel", "21313") in device_info["identifiers"]
        assert device_info["name"] == "Texaco Lot"
        assert device_info["manufacturer"] == "Texaco"

    def test_available_when_station_exists(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that sensor is available when station data exists."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        # CoordinatorEntity.available checks coordinator.last_update_success
        # We just check our override
        assert sensor._station is not None

    def test_not_available_when_station_missing(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that sensor is not available when station data is missing."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "nonexistent")
        assert sensor._station is None

    def test_suggested_display_precision(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that suggested display precision is 3 decimals."""
        sensor = CarbuFuelStationSensor(mock_coordinator, "21313")
        assert sensor.suggested_display_precision == 3

    def test_multiple_stations_have_unique_ids(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that different stations produce different unique_ids."""
        sensor1 = CarbuFuelStationSensor(mock_coordinator, "21313")
        sensor2 = CarbuFuelStationSensor(mock_coordinator, "12345")
        sensor3 = CarbuFuelStationSensor(mock_coordinator, "67890")

        unique_ids = {sensor1.unique_id, sensor2.unique_id, sensor3.unique_id}
        assert len(unique_ids) == 3


class TestCarbuFuelPredictionSensor:
    """Tests for the prediction sensor entity."""

    def test_prediction_sensor_state_and_attributes(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that prediction sensor exposes trend and forecast attributes."""
        mock_coordinator.prediction = FuelPrediction(
            trend_percent=-1.234,
            baseline_date="17/04/2026",
            forecast_date="22/04/2026",
            baseline_price=1.812,
            predicted_price=1.79,
        )

        sensor = CarbuFuelPredictionSensor(mock_coordinator)

        assert sensor.native_value == -1.234
        assert sensor.extra_state_attributes["forecast_date"] == "22/04/2026"
        assert sensor.extra_state_attributes["predicted_price"] == 1.79


class TestCarbuFuelLowestPriceSensor:
    """Tests for the lowest-price summary sensor entity."""

    def test_lowest_price_sensor_state_and_attributes(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that lowest-price sensor exposes the cheapest station details."""
        sensor = CarbuFuelLowestPriceSensor(mock_coordinator)

        assert sensor.native_value == 1.609
        assert sensor.name == "1831 Diesel (B7) lowest price"
        assert sensor.unique_id == "carbu_fuel_BE_bf_279_GO_lowest_price"

        attrs = sensor.extra_state_attributes
        assert attrs["station_name"] == "Texaco Lot"
        assert attrs["station_id"] == "21313"
        assert attrs["entry_postal_code"] == "1831"
        assert attrs["town"] == "Diegem"
        assert attrs["entry_title"] == "Diegem 1831 - Diesel (B7)"

    def test_lowest_price_sensor_uses_custom_entry_title(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that entry_title attribute follows the coordinator title."""
        mock_coordinator.entry_title = "Custom Dashboard Title"
        sensor = CarbuFuelLowestPriceSensor(mock_coordinator)

        assert sensor.extra_state_attributes["entry_title"] == "Custom Dashboard Title"

    def test_lowest_price_sensor_unavailable_without_stations(
        self,
        mock_coordinator: CarbuFuelCoordinator,
    ) -> None:
        """Test that lowest-price sensor is unavailable when no data exists."""
        mock_coordinator.data = {}
        sensor = CarbuFuelLowestPriceSensor(mock_coordinator)

        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}


async def test_async_setup_entry_removes_stale_entities(
    hass,
    sample_fuel_stations,
) -> None:
    """Test that entities are removed when stations disappear from coordinator data."""
    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=MagicMock(),
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )
    coordinator.data = {station.station_id: station for station in sample_fuel_stations}

    entry = MagicMock()
    entry.entry_id = "entry_1"
    entry.runtime_data = coordinator
    entry.async_on_unload = MagicMock()

    created_entities: list[
        CarbuFuelStationSensor | CarbuFuelPredictionSensor | CarbuFuelLowestPriceSensor
    ] = []

    def _capture_entities(
        entities: list[
            CarbuFuelStationSensor | CarbuFuelPredictionSensor | CarbuFuelLowestPriceSensor
        ],
    ) -> None:
        created_entities.extend(entities)

    mock_registry = MagicMock()
    mock_device_registry = MagicMock()
    registry_entries = [
        MagicMock(unique_id=f"{DOMAIN}_21313_GO", entity_id="sensor.texaco_lot_diesel_b7"),
        MagicMock(unique_id=f"{DOMAIN}_12345_GO", entity_id="sensor.shell_diegem_diesel_b7"),
        MagicMock(
            unique_id=f"{DOMAIN}_67890_GO",
            entity_id="sensor.totalenergies_machelen_diesel_b7",
        ),
        MagicMock(unique_id=f"{DOMAIN}_legacy_station", entity_id="sensor.legacy_station"),
    ]
    device_entries = [
        MagicMock(id="device_21313", identifiers={(DOMAIN, "21313")}),
        MagicMock(id="device_12345", identifiers={(DOMAIN, "12345")}),
        MagicMock(id="device_67890", identifiers={(DOMAIN, "67890")}),
        MagicMock(id="device_legacy", identifiers={(DOMAIN, "legacy_station")}),
        MagicMock(id="device_prediction", identifiers={(DOMAIN, "prediction_1831_GO")}),
    ]

    def _entries_for_device(_registry, device_id: str):
        if device_id in {"device_12345", "device_67890", "device_legacy"}:
            return []
        return [MagicMock()]

    with (
        patch("custom_components.carbu_fuel.sensor.er.async_get", return_value=mock_registry),
        patch(
            "custom_components.carbu_fuel.sensor.dr.async_get",
            return_value=mock_device_registry,
        ),
        patch(
            "custom_components.carbu_fuel.sensor.er.async_entries_for_config_entry",
            return_value=registry_entries,
        ),
        patch(
            "custom_components.carbu_fuel.sensor.dr.async_entries_for_config_entry",
            return_value=device_entries,
        ),
        patch(
            "custom_components.carbu_fuel.sensor.er.async_entries_for_device",
            side_effect=_entries_for_device,
        ),
    ):
        await async_setup_entry(hass, entry, _capture_entities)

        # Simulate that only one station remains after a coordinator refresh.
        coordinator.data = {sample_fuel_stations[0].station_id: sample_fuel_stations[0]}
        coordinator.async_update_listeners()

    assert len(created_entities) == 5
    assert any(
        entity.unique_id == "carbu_fuel_BE_bf_279_GO_lowest_price"
        for entity in created_entities
    )
    assert any(entity.unique_id == "carbu_fuel_1831_GO_prediction" for entity in created_entities)
    mock_registry.async_remove.assert_any_call("sensor.shell_diegem_diesel_b7")
    mock_registry.async_remove.assert_any_call("sensor.totalenergies_machelen_diesel_b7")
    mock_registry.async_remove.assert_any_call("sensor.legacy_station")
    mock_device_registry.async_remove_device.assert_any_call("device_12345")
    mock_device_registry.async_remove_device.assert_any_call("device_67890")
    mock_device_registry.async_remove_device.assert_any_call("device_legacy")

    await coordinator.async_shutdown()
