"""Async API client for carbu.com fuel price scraping."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

from .const import (
    CARBU_LOCATION_URL,
    CARBU_LOGO_CDN,
    CARBU_PREDICTION_URL_TEMPLATE,
    CARBU_STATIONS_URL_TEMPLATE,
    USER_AGENT,
    FuelType,
)
from .models import FuelPrediction, FuelStation, Location

_LOGGER = logging.getLogger(__name__)


class CarbuApiError(Exception):
    """Base exception for Carbu API errors."""


class CarbuApiConnectionError(CarbuApiError):
    """Exception for connection errors."""


class CarbuApiParseError(CarbuApiError):
    """Exception for parsing errors."""


class CarbuApiClient:
    """Async client for carbu.com scraping.

    This client is fully separated from Home Assistant code.
    It uses aiohttp for HTTP requests and BeautifulSoup for HTML parsing.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._session = session

    async def _rate_limited_get(self, url: str) -> str:
        """Perform a rate-limited GET request and return the response text."""
        headers = {
            "User-Agent": USER_AGENT,
        }

        try:
            async with self._session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:  # noqa: PLR2004
                    msg = f"HTTP {response.status} from {url}"
                    raise CarbuApiConnectionError(msg)
                return await response.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            msg = f"Error connecting to {url}"
            raise CarbuApiConnectionError(msg) from err

    async def get_locations(self, postal_code: str, country: str) -> list[Location]:
        """Fetch locations matching a postal code from carbu.com.

        Args:
            postal_code: The postal code to search for.
            country: The country code (BE, FR, LU).

        Returns:
            List of matching Location objects.

        Raises:
            CarbuApiConnectionError: On HTTP/network errors.
            CarbuApiParseError: On JSON parsing errors.

        """
        url = f"{CARBU_LOCATION_URL}?location={postal_code}&SHRT=1"
        text = await self._rate_limited_get(url)

        try:
            import json

            raw_locations = json.loads(text)
        except (json.JSONDecodeError, TypeError) as err:
            msg = f"Failed to parse location response for postal code {postal_code}"
            raise CarbuApiParseError(msg) from err

        locations: list[Location] = []
        for item in raw_locations:
            item_country = item.get("c", "")
            item_postal = item.get("pc", "")
            if (
                item_country
                and item_postal
                and item_country.upper() == country.upper()
                and str(item_postal) == str(postal_code)
            ):
                locations.append(Location.from_api_dict(item))

        return locations

    async def get_fuel_stations(
        self,
        town: str,
        postal_code: str,
        location_id: str,
        fuel_type: FuelType,
    ) -> list[FuelStation]:
        """Fetch fuel stations with prices for a location and fuel type.

        Scrapes the carbu.com station listing page for BE/FR/LU.

        Args:
            town: Town name (as returned by carbu.com location search).
            postal_code: Postal code.
            location_id: Carbu.com location ID (e.g. "BE_bf_279").
            fuel_type: The fuel type to query.

        Returns:
            List of FuelStation objects sorted by distance.

        Raises:
            CarbuApiConnectionError: On HTTP/network errors.
            CarbuApiParseError: On HTML parsing errors.

        """
        town_path = quote(town, safe="")
        postal_code_path = quote(postal_code, safe="")
        location_id_path = quote(location_id, safe="")
        url = (
            f"{CARBU_STATIONS_URL_TEMPLATE}/{fuel_type.code}/"
            f"{town_path}/{postal_code_path}/{location_id_path}"
        )
        _LOGGER.debug("Fetching fuel stations from %s", url)
        text = await self._rate_limited_get(url)

        return self._parse_stations_html(text, fuel_type, postal_code)

    async def get_fuel_prediction(self, fuel_type: FuelType) -> FuelPrediction | None:
        """Fetch market-level fuel trend prediction for a supported fuel type.

        Returns None when the selected fuel has no available prediction source.
        """
        prediction_code = fuel_type.prediction_code
        if prediction_code is None:
            return None

        url = CARBU_PREDICTION_URL_TEMPLATE.format(
            prediction_code=quote(prediction_code, safe="")
        )
        _LOGGER.debug("Fetching fuel prediction from %s", url)
        text = await self._rate_limited_get(url)

        return self._parse_prediction_html(text)

    def _parse_stations_html(
        self, html: str, fuel_type: FuelType, postal_code: str
    ) -> list[FuelStation]:
        """Parse the carbu.com station listing HTML into FuelStation objects."""
        soup = BeautifulSoup(html, "html.parser")
        stations: list[FuelStation] = []

        station_grids = soup.find_all("div", class_="stations-grid")

        for grid in station_grids:
            station_contents = grid.find_all("div", class_="station-content")
            for content in station_contents:
                station = self._parse_single_station(content, fuel_type, postal_code)
                if station is not None:
                    stations.append(station)

        stations.sort(key=lambda station: station.distance_km)

        return stations

    def _parse_prediction_html(self, html: str) -> FuelPrediction:
        """Parse prediction chart HTML into a FuelPrediction object."""
        categories_match = re.search(r"categories:\s*\[(.*?)\]", html, re.S)
        series_match = re.search(
            r"name:\s*'Maximum prijs\s*\(Voorspellingen\)'.*?data:\s*\[(.*?)\]",
            html,
            re.S,
        )

        if categories_match is None or series_match is None:
            msg = "Prediction series not found in forecast page"
            raise CarbuApiParseError(msg)

        categories = [
            item.strip().strip("'\"")
            for item in categories_match.group(1).split(",")
            if item.strip()
        ]
        values = _parse_series_float_values(series_match.group(1))

        if "+1" not in categories:
            msg = "Prediction marker '+1' not found in forecast page"
            raise CarbuApiParseError(msg)

        plus_one_index = categories.index("+1")
        if plus_one_index == 0 or plus_one_index + 4 >= len(values):
            msg = "Prediction series does not contain enough data points"
            raise CarbuApiParseError(msg)

        baseline_price = values[plus_one_index - 1]
        predicted_price = values[plus_one_index + 4]

        if baseline_price is None or predicted_price is None or baseline_price <= 0:
            msg = "Prediction contains invalid price values"
            raise CarbuApiParseError(msg)

        baseline_date = categories[plus_one_index - 1]
        forecast_date = _add_days_to_date_str(baseline_date, days=5)
        trend_percent = round(((predicted_price - baseline_price) / baseline_price) * 100, 3)

        return FuelPrediction(
            trend_percent=trend_percent,
            baseline_date=baseline_date,
            forecast_date=forecast_date,
            baseline_price=round(baseline_price, 3),
            predicted_price=round(predicted_price, 3),
        )

    def _parse_single_station(
        self,
        content: BeautifulSoup,
        fuel_type: FuelType,
        postal_code: str,
    ) -> FuelStation | None:
        """Parse a single station-content div into a FuelStation."""
        station_elem = content.find("div", {"id": lambda x: x and x.startswith("item_")})
        if station_elem is None:
            return None

        price_str = station_elem.get("data-price", "")
        if not price_str:
            return None

        try:
            price = float(price_str)
        except (ValueError, TypeError):
            return None

        station_id = station_elem.get("data-id", "")
        name = station_elem.get("data-name", "")
        fuel_name = station_elem.get("data-fuelname", "")
        lat = _safe_float(station_elem.get("data-lat", "0"))
        lng = _safe_float(station_elem.get("data-lng", "0"))
        url = station_elem.get("data-link", "")
        logo_file = station_elem.get("data-logo", "")
        logo_url = f"{CARBU_LOGO_CDN}/{logo_file}" if logo_file else ""
        distance = _safe_float(station_elem.get("data-distance", "0"))

        # Extract brand from URL
        brand = _extract_brand_from_url(url)

        # Parse address
        raw_address = station_elem.get("data-address", "")
        address_parts = raw_address.split("<br/>")
        address = ", ".join(part.strip() for part in address_parts if part.strip())

        # Extract postal code from address (second part: "1651 Lot")
        station_postal = postal_code
        if len(address_parts) > 1:
            second_part = address_parts[1].strip()
            postal_match = re.match(r"(\d+)", second_part)
            if postal_match:
                station_postal = postal_match.group(1)

        if station_postal != postal_code:
            return None

        # Extract city (locality)
        city = ""
        locality_elem = content.find("a", class_="discreteLink")
        if locality_elem:
            span = locality_elem.find("span", itemprop="locality")
            if span:
                city = span.get_text(strip=True)

        # Extract date
        date = ""
        date_match = re.search(r"Update-datum:\s+(\d{2}/\d{2}/\d{2})", content.get_text())
        if date_match:
            date = date_match.group(1)

        # Derive country from location_id prefix or default
        country = "BE"
        if url:
            # URL contains country info like /belgie/ /france/ /luxembourg/
            if "/france/" in url:
                country = "FR"
            elif "/luxembourg/" in url:
                country = "LU"

        return FuelStation(
            station_id=station_id,
            name=name,
            brand=brand,
            fuel_type_code=fuel_type.code,
            fuel_name=fuel_name,
            price=round(price, 3),
            address=address,
            postal_code=station_postal,
            city=city,
            latitude=lat,
            longitude=lng,
            distance_km=round(distance, 2),
            url=url,
            logo_url=logo_url,
            date=date,
            country=country,
        )


def _safe_float(value: str, default: float = 0.0) -> float:
    """Safely convert a string to float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _extract_brand_from_url(url: str) -> str:
    """Extract the brand name from a carbu.com station URL.

    URLs look like: https://carbu.com/belgie/index.php/station/texaco/lot/1651/21313
    """
    try:
        # Split after /station/ and take the brand segment
        if "/station/" in url:
            after_station = url.split("/station/")[1]
            return after_station.split("/")[0].title()
    except (IndexError, AttributeError):
        pass
    return ""


def _parse_series_float_values(raw_series: str) -> list[float | None]:
    """Parse a comma-separated JavaScript number list into floats/None."""
    values: list[float | None] = []

    for token in raw_series.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue

        if cleaned.lower() == "null":
            values.append(None)
            continue

        try:
            values.append(float(cleaned))
        except ValueError:
            values.append(None)

    return values


def _add_days_to_date_str(date_str: str, days: int) -> str:
    """Add days to a date string in common carbu formats, else return input."""
    for date_format in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            date_value = datetime.strptime(date_str, date_format)
            return (date_value + timedelta(days=days)).strftime("%d/%m/%Y")
        except ValueError:
            continue

    return date_str
