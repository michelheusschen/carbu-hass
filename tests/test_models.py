"""Tests for the Carbu Fuel data models."""

from __future__ import annotations

import pytest

from custom_components.carbu_fuel.const import FuelType
from custom_components.carbu_fuel.models import FuelStation, Location


class TestLocation:
    """Tests for the Location dataclass."""

    def test_from_api_dict(self) -> None:
        """Test creating a Location from a carbu.com API dict."""
        api_data = {
            "id": "BE_bf_279",
            "n": "Diegem",
            "pn": "Machelen",
            "c": "BE",
            "cn": "Belgique",
            "pc": "1831",
            "lat": "50.892365",
            "lng": "4.446127",
        }

        location = Location.from_api_dict(api_data)

        assert location.location_id == "BE_bf_279"
        assert location.name == "Diegem"
        assert location.parent_name == "Machelen"
        assert location.country == "BE"
        assert location.postal_code == "1831"
        assert location.latitude == pytest.approx(50.892365)
        assert location.longitude == pytest.approx(4.446127)

    def test_from_api_dict_with_missing_fields(self) -> None:
        """Test that missing fields get default values."""
        location = Location.from_api_dict({})

        assert location.location_id == ""
        assert location.name == ""
        assert location.latitude == 0.0

    def test_is_frozen(self) -> None:
        """Test that Location is immutable."""
        location = Location.from_api_dict({"id": "test", "n": "Test"})
        with pytest.raises(AttributeError):
            location.name = "Modified"  # type: ignore[misc]


class TestFuelStation:
    """Tests for the FuelStation dataclass."""

    def test_is_frozen(self) -> None:
        """Test that FuelStation is immutable."""
        station = FuelStation(
            station_id="1",
            name="Test",
            brand="Test",
            fuel_type_code="GO",
            fuel_name="Diesel",
            price=1.5,
            address="",
            postal_code="",
            city="",
            latitude=0.0,
            longitude=0.0,
            distance_km=0.0,
            url="",
            logo_url="",
            date="",
            country="BE",
        )
        with pytest.raises(AttributeError):
            station.price = 2.0  # type: ignore[misc]


class TestFuelType:
    """Tests for the FuelType enum."""

    def test_code_property(self) -> None:
        assert FuelType.DIESEL_B7.code == "GO"
        assert FuelType.SUPER95_E10.code == "E10"
        assert FuelType.LPG.code == "GPL"

    def test_label_property(self) -> None:
        assert FuelType.DIESEL_B7.label == "Diesel (B7)"
        assert FuelType.SUPER95_E10.label == "Super 95 (E10)"

    def test_from_code(self) -> None:
        assert FuelType.from_code("GO") is FuelType.DIESEL_B7
        assert FuelType.from_code("E10") is FuelType.SUPER95_E10

    def test_from_code_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown fuel type"):
            FuelType.from_code("UNKNOWN")
