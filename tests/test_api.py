"""Tests for the Carbu API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.carbu_fuel.api import (
    CarbuApiClient,
    CarbuApiConnectionError,
    CarbuApiParseError,
)
from custom_components.carbu_fuel.const import FuelType


class _MockResponse:
    """Minimal async context manager for mocked aiohttp responses."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self) -> _MockResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def text(self) -> str:
        return self._body


class TestRateLimitedGet:
    """Tests for CarbuApiClient._rate_limited_get."""

    async def test_successful_request_returns_text(self, mock_session) -> None:
        """Test successful request path without patching internal aiohttp usage."""
        mock_session.get.return_value = _MockResponse(200, "ok")
        client = CarbuApiClient(mock_session)

        text = await client._rate_limited_get("https://example.invalid")

        assert text == "ok"


class TestGetLocations:
    """Tests for CarbuApiClient.get_locations."""

    async def test_returns_matching_locations(
        self, api_client: CarbuApiClient, sample_location_api_response: str
    ) -> None:
        """Test that locations matching postal code and country are returned."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_location_api_response

            locations = await api_client.get_locations("1831", "BE")

            assert len(locations) == 1
            assert locations[0].location_id == "BE_bf_279"
            assert locations[0].name == "Diegem"
            assert locations[0].parent_name == "Machelen"
            assert locations[0].country == "BE"
            assert locations[0].postal_code == "1831"
            assert locations[0].latitude == pytest.approx(50.892365)
            assert locations[0].longitude == pytest.approx(4.446127)

    async def test_filters_by_country(
        self, api_client: CarbuApiClient, sample_location_api_response: str
    ) -> None:
        """Test that only locations from the requested country are returned."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_location_api_response

            locations = await api_client.get_locations("1831", "LU")

            assert len(locations) == 1
            assert locations[0].location_id == "LU_lx_3287"
            assert locations[0].country == "LU"

    async def test_returns_empty_for_no_match(
        self, api_client: CarbuApiClient, sample_location_api_response: str
    ) -> None:
        """Test that an empty list is returned if no postal code matches."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_location_api_response

            locations = await api_client.get_locations("9999", "BE")
            assert locations == []

    async def test_connection_error_propagates(self, api_client: CarbuApiClient) -> None:
        """Test that connection errors from the HTTP request propagate."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = CarbuApiConnectionError("timeout")

            with pytest.raises(CarbuApiConnectionError):
                await api_client.get_locations("1831", "BE")

    async def test_invalid_json_raises_parse_error(self, api_client: CarbuApiClient) -> None:
        """Test that invalid JSON raises CarbuApiParseError."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "not valid json{{"

            with pytest.raises(CarbuApiParseError):
                await api_client.get_locations("1831", "BE")


class TestGetFuelStations:
    """Tests for CarbuApiClient.get_fuel_stations."""

    async def test_parses_stations_from_html(
        self, api_client: CarbuApiClient, sample_stations_html: str
    ) -> None:
        """Test that stations are correctly parsed from HTML."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_stations_html

            stations = await api_client.get_fuel_stations(
                town="Diegem",
                postal_code="1831",
                location_id="BE_bf_279",
                fuel_type=FuelType.DIESEL_B7,
            )

            assert len(stations) == 1

    async def test_station_fields_are_correct(
        self, api_client: CarbuApiClient, sample_stations_html: str
    ) -> None:
        """Test that individual station fields are correctly parsed."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_stations_html

            stations = await api_client.get_fuel_stations(
                town="Diegem",
                postal_code="1831",
                location_id="BE_bf_279",
                fuel_type=FuelType.DIESEL_B7,
            )

            station = stations[0]
            assert station.station_id == "12345"
            assert station.name == "Shell Diegem"
            assert station.brand == "Shell"
            assert station.price == 1.649
            assert station.fuel_name == "Diesel (B7)"
            assert station.distance_km == 0.5
            assert station.latitude == pytest.approx(50.893, abs=0.001)
            assert station.city == "Diegem"
            assert station.date == "16/04/26"

    async def test_skips_stations_without_price(
        self, api_client: CarbuApiClient, sample_stations_html: str
    ) -> None:
        """Test that stations with empty price are excluded."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_stations_html

            stations = await api_client.get_fuel_stations(
                town="Diegem",
                postal_code="1831",
                location_id="BE_bf_279",
                fuel_type=FuelType.DIESEL_B7,
            )

            station_ids = [s.station_id for s in stations]
            assert station_ids == ["12345"]
            assert "99999" not in station_ids

    async def test_connection_error_propagates(self, api_client: CarbuApiClient) -> None:
        """Test that connection errors are propagated."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = CarbuApiConnectionError("timeout")

            with pytest.raises(CarbuApiConnectionError):
                await api_client.get_fuel_stations(
                    town="Diegem",
                    postal_code="1831",
                    location_id="BE_bf_279",
                    fuel_type=FuelType.DIESEL_B7,
                )

    async def test_empty_html_returns_empty_list(self, api_client: CarbuApiClient) -> None:
        """Test that empty/minimal HTML returns an empty list."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "<html><body></body></html>"

            stations = await api_client.get_fuel_stations(
                town="Diegem",
                postal_code="1831",
                location_id="BE_bf_279",
                fuel_type=FuelType.DIESEL_B7,
            )

            assert stations == []

    async def test_brand_extraction_from_url(
        self, api_client: CarbuApiClient, sample_stations_html: str
    ) -> None:
        """Test that brand is correctly extracted from station URL."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_stations_html

            stations = await api_client.get_fuel_stations(
                town="Diegem",
                postal_code="1831",
                location_id="BE_bf_279",
                fuel_type=FuelType.DIESEL_B7,
            )

            brands = {s.station_id: s.brand for s in stations}
            assert brands["12345"] == "Shell"
            assert "21313" not in brands
            assert "67890" not in brands

    async def test_town_is_url_encoded_in_station_request(
        self, api_client: CarbuApiClient, sample_stations_html: str
    ) -> None:
        """Test that town names are URL-encoded in station requests."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = sample_stations_html

            await api_client.get_fuel_stations(
                town="L'Hay les Roses",
                postal_code="94240",
                location_id="FR_11_94_942_9401_94038",
                fuel_type=FuelType.DIESEL_B7,
            )

            called_url = mock_get.call_args.args[0]
            assert "/L%27Hay%20les%20Roses/" in called_url

    async def test_excludes_regional_section_stations(self, api_client: CarbuApiClient) -> None:
        """Test that stations outside requested postal code are excluded."""
        html = """
        <html>
          <body>
            <div class="stations-grid row">
              <div class="station-content col-xs-12">
                <div id="item_100"
                     data-lat="50.95"
                     data-lng="5.69"
                     data-id="100"
                     data-name="Local Station"
                     data-fuelname="Super 95 (E10)"
                     data-price="1.740"
                     data-distance="1.2"
                     data-link="https://carbu.com/station/local/3630/100"
                     data-address="Main Street 1<br/>3630 Maasmechelen"
                     class="stationItem panel panel-default"></div>
                <a class="discreteLink" href="#">
                  <span itemprop="locality">Maasmechelen</span>
                </a>
                <span>Update-datum: 18/04/26</span>
              </div>
            </div>
            <h2 class="h2-station-services">In de regio van Maasmechelen</h2>
            <div class="stations-grid row">
              <div class="station-content col-xs-12">
                <div id="item_200"
                     data-lat="50.93"
                     data-lng="5.68"
                     data-id="200"
                     data-name="Regional Station"
                     data-fuelname="Super 95 (E10)"
                     data-price="1.799"
                     data-distance="7.5"
                     data-link="https://carbu.com/station/regional/3621/200"
                     data-address="Region Road 10<br/>3621 Rekem"
                     class="stationItem panel panel-default"></div>
                <a class="discreteLink" href="#">
                  <span itemprop="locality">Rekem</span>
                </a>
                <span>Update-datum: 18/04/26</span>
              </div>
            </div>
          </body>
        </html>
        """

        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html

            stations = await api_client.get_fuel_stations(
                town="Maasmechelen",
                postal_code="3630",
                location_id="BE_li_642",
                fuel_type=FuelType.SUPER95_E10,
            )

            assert len(stations) == 1
            assert stations[0].station_id == "100"

    async def test_stations_are_sorted_by_distance(self, api_client: CarbuApiClient) -> None:
        """Test that parsed stations are returned sorted by distance."""
        html = """
        <html>
          <body>
            <div class="stations-grid row">
              <div class="station-content col-xs-12">
                <div id="item_far"
                     data-lat="50.9"
                     data-lng="5.6"
                     data-id="far"
                     data-name="Far Station"
                     data-fuelname="Diesel (B7)"
                     data-price="1.800"
                     data-distance="8.1"
                     data-link="https://carbu.com/station/far/3630/1"
                     data-address="Far Road 1<br/>3630 Maasmechelen"
                     class="stationItem panel panel-default"></div>
                <a class="discreteLink" href="#">
                  <span itemprop="locality">Maasmechelen</span>
                </a>
                <span>Update-datum: 18/04/26</span>
              </div>
              <div class="station-content col-xs-12">
                <div id="item_near"
                     data-lat="50.95"
                     data-lng="5.69"
                     data-id="near"
                     data-name="Near Station"
                     data-fuelname="Diesel (B7)"
                     data-price="1.700"
                     data-distance="1.3"
                     data-link="https://carbu.com/station/near/3630/2"
                     data-address="Near Road 2<br/>3630 Maasmechelen"
                     class="stationItem panel panel-default"></div>
                <a class="discreteLink" href="#">
                  <span itemprop="locality">Maasmechelen</span>
                </a>
                <span>Update-datum: 18/04/26</span>
              </div>
            </div>
          </body>
        </html>
        """

        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html

            stations = await api_client.get_fuel_stations(
                town="Maasmechelen",
                postal_code="3630",
                location_id="BE_li_642",
                fuel_type=FuelType.DIESEL_B7,
            )

            assert [station.station_id for station in stations] == ["near", "far"]


class TestGetFuelPrediction:
    """Tests for CarbuApiClient.get_fuel_prediction."""

    async def test_returns_prediction_for_supported_fuel(
        self,
        api_client: CarbuApiClient,
    ) -> None:
        """Test that prediction data is parsed for supported fuel types."""
        html = """
        <html><body>
        <script>
        categories: ['15/04/2026', '16/04/2026', '17/04/2026', '+1', '+2', '+3', '+4', '+5']
        series: [
            {
                name: 'Maximum prijs  (Voorspellingen)',
                data: [1.78, 1.79, 1.80, 1.81, 1.82, 1.83, 1.84, 1.85]
            }
        ]
        });
        </script>
        </body></html>
        """

        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = html

            prediction = await api_client.get_fuel_prediction(FuelType.DIESEL_B7)

            assert prediction is not None
            assert prediction.baseline_date == "17/04/2026"
            assert prediction.forecast_date == "22/04/2026"
            assert prediction.baseline_price == 1.8
            assert prediction.predicted_price == 1.85
            assert prediction.trend_percent == pytest.approx(2.778, abs=0.001)

    async def test_returns_none_for_unsupported_fuel(
        self,
        api_client: CarbuApiClient,
    ) -> None:
        """Test that unsupported fuels return no prediction."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            prediction = await api_client.get_fuel_prediction(FuelType.SUPER98_E5)

            assert prediction is None
            mock_get.assert_not_called()

    async def test_invalid_prediction_html_raises_parse_error(
        self,
        api_client: CarbuApiClient,
    ) -> None:
        """Test that malformed prediction HTML raises CarbuApiParseError."""
        with patch.object(api_client, "_rate_limited_get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "<html><body>No chart here</body></html>"

            with pytest.raises(CarbuApiParseError):
                await api_client.get_fuel_prediction(FuelType.SUPER95_E10)
