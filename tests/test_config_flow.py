"""Tests for the Carbu Fuel config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.carbu_fuel.const import (
    CONF_COUNTRY,
    CONF_FUEL_TYPE,
    CONF_LOCATION_ID,
    CONF_POSTAL_CODE,
    CONF_TOWN,
    DOMAIN,
)
from custom_components.carbu_fuel.models import Location

# The pytest-homeassistant-custom-component fixture `hass` provides a HA
# instance but doesn't automatically discover custom_components.
# We need to patch the loader so it can find our config flow.

MOCK_LOCATION = Location(
    location_id="BE_bf_279",
    name="Diegem",
    parent_name="Machelen",
    country="BE",
    postal_code="1831",
    latitude=50.892365,
    longitude=4.446127,
)


@pytest.fixture(autouse=True)
def _register_integration(hass):
    """Register the carbu_fuel integration with Home Assistant's loader."""
    from homeassistant.loader import Integration

    integration = Integration(
        hass,
        "custom_components.carbu_fuel",
        None,
        {
            "name": "Carbu Fuel Prices",
            "domain": DOMAIN,
            "config_flow": True,
            "documentation": "https://github.com/michelheusschen/carbu-hass",
            "requirements": [],
            "dependencies": [],
            "codeowners": [],
            "version": "1.0.0",
            "iot_class": "cloud_polling",
        },
    )
    hass.data.setdefault("integrations", {})[DOMAIN] = integration


@pytest.fixture(autouse=True)
def _prevent_entry_setup() -> Generator[None]:
    """Keep config flow tests focused on the flow, not entry setup side effects."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_setup",
        new=AsyncMock(return_value=True),
    ), patch(
        "custom_components.carbu_fuel.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        yield


def _patch_locations_api(locations: list[Location]):
    """Patch CarbuApiClient.get_locations to return the given locations."""
    return patch(
        "custom_components.carbu_fuel.config_flow.CarbuApiClient",
        return_value=MagicMock(
            get_locations=AsyncMock(return_value=locations),
        ),
    )


def _patch_fuel_api(stations: list[object] | None = None):
    """Patch CarbuApiClient.get_fuel_stations for fuel availability checks."""
    return patch(
        "custom_components.carbu_fuel.config_flow.CarbuApiClient",
        return_value=MagicMock(
            get_fuel_stations=AsyncMock(
                return_value=stations if stations is not None else [MagicMock()]
            ),
        ),
    )


async def test_full_flow_single_town(hass) -> None:
    """Test complete config flow when postal code matches a single town."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit location — single match, should skip town step
    with _patch_locations_api([MOCK_LOCATION]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    # Should go directly to fuel_type step (single town match)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "fuel_type"

    # Submit fuel type
    with _patch_fuel_api():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FUEL_TYPE: "GO"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Diegem 1831 — Diesel (B7)"
    assert result["data"] == {
        CONF_COUNTRY: "BE",
        CONF_POSTAL_CODE: "1831",
        CONF_TOWN: "Diegem",
        CONF_LOCATION_ID: "BE_bf_279",
        CONF_FUEL_TYPE: "GO",
    }

    await hass.async_block_till_done()
    await hass.async_stop(force=True)


async def test_full_flow_multiple_towns(hass) -> None:
    """Test config flow when postal code matches multiple towns."""
    locations = [
        MOCK_LOCATION,
        Location(
            location_id="BE_bf_280",
            name="Perk",
            parent_name="Steenokkerzeel",
            country="BE",
            postal_code="1831",
            latitude=50.93,
            longitude=4.48,
        ),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api(locations):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    # Should show town selection step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "town"

    # Select a town
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOWN: "BE_bf_279"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "fuel_type"

    # Select fuel type
    with _patch_fuel_api():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FUEL_TYPE: "E10"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOWN] == "Diegem"
    assert result["data"][CONF_FUEL_TYPE] == "E10"


async def test_connection_error_shows_error(hass) -> None:
    """Test that connection errors show an error message."""
    from custom_components.carbu_fuel.api import CarbuApiConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.carbu_fuel.config_flow.CarbuApiClient",
        return_value=MagicMock(
            get_locations=AsyncMock(side_effect=CarbuApiConnectionError("timeout")),
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_locations_found_shows_error(hass) -> None:
    """Test that no matching locations shows an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api([]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "9999"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_POSTAL_CODE: "no_locations_found"}


async def test_duplicate_entry_aborts(hass) -> None:
    """Test that configuring the same location+fuel type aborts."""
    # Create a first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api([MOCK_LOCATION]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    with _patch_fuel_api():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FUEL_TYPE: "GO"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Try to create the same entry — should abort
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api([MOCK_LOCATION]):
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    with _patch_fuel_api():
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_FUEL_TYPE: "GO"},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_no_stations_for_fuel_shows_error(hass) -> None:
    """Test that selecting an unavailable fuel shows a field error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api([MOCK_LOCATION]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "BE", CONF_POSTAL_CODE: "1831"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "fuel_type"

    with _patch_fuel_api([]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FUEL_TYPE: "DB10"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "fuel_type"
    assert result["errors"] == {CONF_FUEL_TYPE: "no_stations_for_fuel"}


async def test_town_selection_uses_location_id_when_names_collide(hass) -> None:
    """Test town selection stays deterministic when names are duplicated."""
    duplicate_name_locations = [
        Location(
            location_id="LU_lx_3195",
            name="Luxembourg",
            parent_name="Luxembourg",
            country="LU",
            postal_code="1616",
            latitude=49.610004,
            longitude=6.129596,
        ),
        Location(
            location_id="LU_lx_9999",
            name="Luxembourg",
            parent_name="Second District",
            country="LU",
            postal_code="1616",
            latitude=49.600000,
            longitude=6.100000,
        ),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_locations_api(duplicate_name_locations):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_COUNTRY: "LU", CONF_POSTAL_CODE: "1616"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "town"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOWN: "LU_lx_9999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "fuel_type"

    with _patch_fuel_api():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FUEL_TYPE: "GO"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOCATION_ID] == "LU_lx_9999"
    assert result["data"][CONF_TOWN] == "Luxembourg"
