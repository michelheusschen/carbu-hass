"""Tests for the CarbuFuelCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.carbu_fuel.api import CarbuApiClient, CarbuApiConnectionError
from custom_components.carbu_fuel.const import FuelType
from custom_components.carbu_fuel.coordinator import CarbuFuelCoordinator
from custom_components.carbu_fuel.models import FuelPrediction, FuelStation


async def test_successful_fetch(
    hass,
    sample_fuel_stations: list[FuelStation],
) -> None:
    """Test that coordinator stores station data on successful fetch."""
    mock_client = MagicMock(spec=CarbuApiClient)
    mock_client.get_fuel_stations = AsyncMock(return_value=sample_fuel_stations)
    mock_client.get_fuel_prediction = AsyncMock(
        return_value=FuelPrediction(
            trend_percent=-1.2,
            baseline_date="17/04/2026",
            forecast_date="22/04/2026",
            baseline_price=1.8,
            predicted_price=1.78,
        )
    )

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=mock_client,
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    data = await coordinator._async_update_data()

    assert len(data) == 3
    assert "21313" in data
    assert "12345" in data
    assert "67890" in data
    assert data["21313"].price == 1.609
    assert data["12345"].name == "Shell Diegem"
    assert coordinator.prediction is not None
    assert coordinator.prediction.trend_percent == -1.2


async def test_api_error_raises_update_failed(hass) -> None:
    """Test that API errors are wrapped in UpdateFailed."""
    mock_client = MagicMock(spec=CarbuApiClient)
    mock_client.get_fuel_stations = AsyncMock(side_effect=CarbuApiConnectionError("timeout"))
    mock_client.get_fuel_prediction = AsyncMock(return_value=None)

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=mock_client,
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    with pytest.raises(UpdateFailed, match="Error fetching"):
        await coordinator._async_update_data()


async def test_empty_station_list(hass) -> None:
    """Test that coordinator handles empty station lists."""
    mock_client = MagicMock(spec=CarbuApiClient)
    mock_client.get_fuel_stations = AsyncMock(return_value=[])
    mock_client.get_fuel_prediction = AsyncMock(return_value=None)

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=mock_client,
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    data = await coordinator._async_update_data()

    assert data == {}


async def test_data_keyed_by_station_id(
    hass,
    sample_fuel_stations: list[FuelStation],
) -> None:
    """Test that data dict is keyed by station_id."""
    mock_client = MagicMock(spec=CarbuApiClient)
    mock_client.get_fuel_stations = AsyncMock(return_value=sample_fuel_stations)
    mock_client.get_fuel_prediction = AsyncMock(return_value=None)

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=mock_client,
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    data = await coordinator._async_update_data()

    for station in sample_fuel_stations:
        assert station.station_id in data
        assert data[station.station_id] is station


async def test_prediction_error_does_not_fail_station_update(
    hass,
    sample_fuel_stations: list[FuelStation],
) -> None:
    """Test that prediction fetch errors do not fail station refresh."""
    mock_client = MagicMock(spec=CarbuApiClient)
    mock_client.get_fuel_stations = AsyncMock(return_value=sample_fuel_stations)
    mock_client.get_fuel_prediction = AsyncMock(side_effect=CarbuApiConnectionError("timeout"))

    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=mock_client,
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    data = await coordinator._async_update_data()

    assert len(data) == 3
    assert coordinator.prediction is None


def test_entry_title_uses_explicit_value(hass) -> None:
    """Test that an explicit entry title is preserved on the coordinator."""
    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=MagicMock(spec=CarbuApiClient),
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
        entry_title="My Custom Title",
    )

    assert coordinator.entry_title == "My Custom Title"


def test_entry_title_has_default_fallback(hass) -> None:
    """Test that coordinator builds a sensible default entry title."""
    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=MagicMock(spec=CarbuApiClient),
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )

    assert coordinator.entry_title == "Diegem 1831 - Diesel (B7)"
