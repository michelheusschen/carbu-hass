"""Constants for the Carbu Fuel Prices integration."""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

DOMAIN = "carbu_fuel"
DEFAULT_SCAN_INTERVAL = timedelta(hours=2)

SUPPORTED_COUNTRIES = ["BE", "FR", "LU"]

# Config entry keys
CONF_COUNTRY = "country"
CONF_POSTAL_CODE = "postal_code"
CONF_TOWN = "town"
CONF_LOCATION_ID = "location_id"
CONF_FUEL_TYPE = "fuel_type"

# Carbu.com base URLs
CARBU_BASE_URL = "https://carbu.com"
CARBU_LOCATION_URL = f"{CARBU_BASE_URL}/commonFunctions/getlocation/controller.getlocation_JSON.php"
CARBU_STATIONS_URL_TEMPLATE = f"{CARBU_BASE_URL}/belgie/liste-stations-service"
CARBU_PREDICTION_URL_TEMPLATE = (
    f"{CARBU_BASE_URL}/belgie/index.php/voorspellingen?p=M&C={{prediction_code}}"
)

# Logo CDN
CARBU_LOGO_CDN = "https://carbucomstatic-5141.kxcdn.com/brandLogo"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)


class FuelType(Enum):
    """Available fuel types on carbu.com for BE/FR/LU."""

    SUPER95_E10 = ("E10", "Super 95 (E10)")
    SUPER98_E5 = ("SP98", "Super 98 (E5)")
    SUPER98_E10 = ("E10_98", "Super 98 (E10)")
    DIESEL_B7 = ("GO", "Diesel (B7)")
    DIESEL_B10 = ("DB10", "Diesel (B10)")
    DIESEL_XTL = ("DXTL", "Diesel (XTL)")
    DIESEL_PLUS = ("GO_plus", "Diesel+")
    LPG = ("GPL", "LPG")
    CNG = ("CNG", "CNG")

    @property
    def code(self) -> str:
        """Return the carbu.com URL code for this fuel type."""
        return self.value[0]

    @property
    def label(self) -> str:
        """Return a human-readable label for this fuel type."""
        return self.value[1]

    @property
    def prediction_code(self) -> str | None:
        """Return the Carbu prediction page code when available for this fuel."""
        if self == FuelType.SUPER95_E10:
            return "E95"

        if self in {
            FuelType.DIESEL_B7,
            FuelType.DIESEL_B10,
            FuelType.DIESEL_XTL,
            FuelType.DIESEL_PLUS,
        }:
            return "D"

        return None

    @classmethod
    def from_code(cls, code: str) -> FuelType:
        """Look up a FuelType by its carbu.com code."""
        for member in cls:
            if member.code == code:
                return member
        msg = f"Unknown fuel type code: {code}"
        raise ValueError(msg)
