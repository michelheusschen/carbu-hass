"""Test fixtures for carbu_fuel tests."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Generator
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HassJob, HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component import plugins as ha_plugins
from pytest_homeassistant_custom_component.plugins import (
    get_scheduled_timer_handles,
    long_repr_strings,
)

from custom_components.carbu_fuel.api import CarbuApiClient
from custom_components.carbu_fuel.const import FuelType
from custom_components.carbu_fuel.coordinator import CarbuFuelCoordinator
from custom_components.carbu_fuel.models import FuelStation, Location

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None]:
    """Verify test cleanup while allowing HA's shutdown helper thread."""
    threads_before = frozenset(threading.enumerate())
    tasks_before = asyncio.all_tasks(event_loop)
    yield

    event_loop.run_until_complete(event_loop.shutdown_default_executor())

    if len(ha_plugins.INSTANCES) >= 2:
        count = len(ha_plugins.INSTANCES)
        for inst in ha_plugins.INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

    tasks = asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        if expected_lingering_tasks:
            ha_plugins._LOGGER.warning("Lingering task after test %r", task)
        else:
            pytest.fail(f"Lingering task after test {task!r}")
        task.cancel()
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))

    for handle in get_scheduled_timer_handles(event_loop):
        if not handle.cancelled():
            with long_repr_strings():
                if expected_lingering_timers:
                    ha_plugins._LOGGER.warning("Lingering timer after test %r", handle)
                elif handle._args and isinstance(job := handle._args[-1], HassJob):
                    if job.cancel_on_shutdown:
                        continue
                    pytest.fail(f"Lingering timer after job {job!r}")
                else:
                    pytest.fail(f"Lingering timer after test {handle!r}")
                handle.cancel()

    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        assert (
            isinstance(thread, threading._DummyThread)
            or thread.name.startswith("waitpid-")
            or thread.name.endswith("(_run_safe_shutdown_loop)")
        )

    try:
        assert dt_util.DEFAULT_TIME_ZONE is UTC
    finally:
        dt_util.DEFAULT_TIME_ZONE = UTC


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp ClientSession."""
    return MagicMock()


@pytest.fixture
def api_client(mock_session: MagicMock) -> CarbuApiClient:
    """Create a CarbuApiClient with a mock session."""
    return CarbuApiClient(mock_session)


@pytest.fixture
def sample_locations() -> list[Location]:
    """Return sample Location objects."""
    return [
        Location(
            location_id="BE_bf_279",
            name="Diegem",
            parent_name="Machelen",
            country="BE",
            postal_code="1831",
            latitude=50.892365,
            longitude=4.446127,
        ),
    ]


@pytest.fixture
def sample_fuel_stations() -> list[FuelStation]:
    """Return sample FuelStation objects."""
    return [
        FuelStation(
            station_id="21313",
            name="Texaco Lot",
            brand="Texaco",
            fuel_type_code="GO",
            fuel_name="Diesel (B7)",
            price=1.609,
            address="Bergensesteenweg 155, 1651 Lot",
            postal_code="1651",
            city="Lot",
            latitude=50.768739,
            longitude=4.258758,
            distance_km=5.53,
            url="https://carbu.com/belgie/index.php/station/texaco/lot/1651/21313",
            logo_url="https://carbucomstatic-5141.kxcdn.com/brandLogo/texaco.gif",
            date="15/04/26",
            country="BE",
        ),
        FuelStation(
            station_id="12345",
            name="Shell Diegem",
            brand="Shell",
            fuel_type_code="GO",
            fuel_name="Diesel (B7)",
            price=1.649,
            address="Haachtsesteenweg 10, 1831 Diegem",
            postal_code="1831",
            city="Diegem",
            latitude=50.893,
            longitude=4.447,
            distance_km=0.5,
            url="https://carbu.com/belgie/index.php/station/shell/diegem/1831/12345",
            logo_url="https://carbucomstatic-5141.kxcdn.com/brandLogo/shell.gif",
            date="16/04/26",
            country="BE",
        ),
        FuelStation(
            station_id="67890",
            name="TotalEnergies Machelen",
            brand="Totalenergies",
            fuel_type_code="GO",
            fuel_name="Diesel (B7)",
            price=1.639,
            address="Woluwelaan 50, 1830 Machelen",
            postal_code="1830",
            city="Machelen",
            latitude=50.900,
            longitude=4.440,
            distance_km=1.2,
            url="https://carbu.com/belgie/index.php/station/totalenergies/machelen/1830/67890",
            logo_url="https://carbucomstatic-5141.kxcdn.com/brandLogo/totalenergies.gif",
            date="16/04/26",
            country="BE",
        ),
    ]


@pytest.fixture
def sample_location_api_response() -> str:
    """Return a sample carbu.com location API JSON response."""
    return json.dumps(
        [
            {
                "id": "BE_bf_279",
                "n": "Diegem",
                "pn": "Machelen",
                "c": "BE",
                "cn": "Belgique",
                "pc": "1831",
                "lat": "50.892365",
                "lng": "4.446127",
            },
            {
                "id": "LU_lx_3287",
                "n": "Luxembourg",
                "pn": "Luxembourg",
                "c": "LU",
                "cn": "Luxembourg",
                "pc": "1831",
                "lat": "49.610004",
                "lng": "6.129596",
            },
        ]
    )


@pytest.fixture
def sample_stations_html() -> str:
    """Return sample carbu.com station listing HTML."""
    return (FIXTURES_DIR / "stations_be_diesel.html").read_text()


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant,
    sample_fuel_stations: list[FuelStation],
) -> CarbuFuelCoordinator:
    """Create a mock coordinator with sample data."""
    coordinator = CarbuFuelCoordinator(
        hass=hass,
        api_client=MagicMock(),
        town="Diegem",
        postal_code="1831",
        location_id="BE_bf_279",
        fuel_type=FuelType.DIESEL_B7,
    )
    coordinator.data = {s.station_id: s for s in sample_fuel_stations}
    return coordinator
