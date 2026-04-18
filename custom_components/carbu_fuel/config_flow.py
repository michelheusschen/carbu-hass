"""Config flow for the Carbu Fuel Prices integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import CarbuApiClient, CarbuApiError
from .const import (
    CONF_COUNTRY,
    CONF_FUEL_TYPE,
    CONF_LOCATION_ID,
    CONF_POSTAL_CODE,
    CONF_TOWN,
    DOMAIN,
    SUPPORTED_COUNTRIES,
    FuelType,
)
from .models import Location

_LOGGER = logging.getLogger(__name__)


class CarbuFuelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Carbu Fuel Prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._locations: list[Location] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the first step: country and postal code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            # Fetch matching locations from carbu.com
            session = async_get_clientsession(self.hass)
            client = CarbuApiClient(session)

            try:
                self._locations = await client.get_locations(
                    postal_code=user_input[CONF_POSTAL_CODE],
                    country=user_input[CONF_COUNTRY],
                )
            except CarbuApiError:
                errors["base"] = "cannot_connect"
            else:
                if not self._locations:
                    errors[CONF_POSTAL_CODE] = "no_locations_found"
                elif len(self._locations) == 1:
                    # Only one town match — skip town selection
                    loc = self._locations[0]
                    self._data[CONF_TOWN] = loc.name
                    self._data[CONF_LOCATION_ID] = loc.location_id
                    return await self.async_step_fuel_type()
                else:
                    return await self.async_step_town()

        country_options = [SelectOptionDict(value=c, label=c) for c in SUPPORTED_COUNTRIES]

        schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY, default="BE"): SelectSelector(
                    SelectSelectorConfig(
                        options=country_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_POSTAL_CODE): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_town(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the town selection step."""
        if user_input is not None:
            selected_location_id = user_input[CONF_TOWN]
            location = next(
                (loc for loc in self._locations if loc.location_id == selected_location_id),
                None,
            )
            if location:
                self._data[CONF_TOWN] = location.name
                self._data[CONF_LOCATION_ID] = location.location_id
                return await self.async_step_fuel_type()

        town_options = [
            SelectOptionDict(
                value=loc.location_id,
                label=f"{loc.name} ({loc.parent_name})" if loc.parent_name else loc.name,
            )
            for loc in self._locations
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_TOWN): SelectSelector(
                    SelectSelectorConfig(
                        options=town_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="town",
            data_schema=schema,
        )

    async def async_step_fuel_type(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the fuel type selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_fuel_code = user_input[CONF_FUEL_TYPE]
            fuel_type = FuelType.from_code(selected_fuel_code)

            # Validate that this location+fuel combination currently returns stations.
            session = async_get_clientsession(self.hass)
            client = CarbuApiClient(session)
            try:
                stations = await client.get_fuel_stations(
                    town=self._data[CONF_TOWN],
                    postal_code=self._data[CONF_POSTAL_CODE],
                    location_id=self._data[CONF_LOCATION_ID],
                    fuel_type=fuel_type,
                )
            except CarbuApiError:
                errors["base"] = "cannot_connect"
            else:
                if not stations:
                    errors[CONF_FUEL_TYPE] = "no_stations_for_fuel"

            if not errors:
                self._data[CONF_FUEL_TYPE] = selected_fuel_code

                # Set unique ID to prevent duplicate entries
                unique_id = f"{self._data[CONF_LOCATION_ID]}_{self._data[CONF_FUEL_TYPE]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = (
                    f"{self._data[CONF_TOWN]} "
                    f"{self._data[CONF_POSTAL_CODE]} — "
                    f"{FuelType.from_code(self._data[CONF_FUEL_TYPE]).label}"
                )
                return self.async_create_entry(title=title, data=self._data)

        fuel_options = [SelectOptionDict(value=ft.code, label=ft.label) for ft in FuelType]

        schema = vol.Schema(
            {
                vol.Required(CONF_FUEL_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=fuel_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="fuel_type",
            data_schema=schema,
            errors=errors,
        )
