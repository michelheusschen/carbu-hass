"""Data models for the Carbu Fuel Prices integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A location as returned by carbu.com's location search."""

    location_id: str
    name: str
    parent_name: str
    country: str
    postal_code: str
    latitude: float
    longitude: float

    @classmethod
    def from_api_dict(cls, data: dict) -> Location:
        """Create a Location from carbu.com's JSON response dict."""
        return cls(
            location_id=data.get("id", ""),
            name=data.get("n", ""),
            parent_name=data.get("pn", ""),
            country=data.get("c", ""),
            postal_code=data.get("pc", ""),
            latitude=float(data.get("lat", 0)),
            longitude=float(data.get("lng", 0)),
        )


@dataclass(frozen=True)
class FuelStation:
    """A fuel station with price information."""

    station_id: str
    name: str
    brand: str
    fuel_type_code: str
    fuel_name: str
    price: float
    address: str
    postal_code: str
    city: str
    latitude: float
    longitude: float
    distance_km: float
    url: str
    logo_url: str
    date: str
    country: str


@dataclass(frozen=True)
class FuelPrediction:
    """Fuel price prediction data parsed from carbu.com forecast page."""

    trend_percent: float
    baseline_date: str
    forecast_date: str
    baseline_price: float
    predicted_price: float
