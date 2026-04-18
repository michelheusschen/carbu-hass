# Carbu Fuel Prices (Home Assistant Custom Integration)

Home Assistant custom integration that fetches fuel prices from carbu.com for Belgium, France, and Luxembourg.

## Features

- Config flow for country, postal code, town, and fuel type selection.
- Per-station fuel sensors with rich attributes (brand, address, distance, map URL, coordinates, timestamp).
- Native lowest-price sensor per configured entry.
- Market trend prediction sensor (for supported fuel families).
- Automatic cleanup of stale station entities and devices.

## Supported Countries

- BE
- FR
- LU

## Supported Fuel Types

- Super 95 (E10)
- Super 98 (E5)
- Super 98 (E10)
- Diesel (B7)
- Diesel (B10)
- Diesel (XTL)
- Diesel+
- LPG
- CNG

## Installation

### Option A: HACS (recommended)

1. In HACS, add `https://github.com/michelheusschen/carbu-hass` as a custom repository.
2. Category: Integration.
3. Install Carbu Fuel Prices.
4. Restart Home Assistant.

### Option B: Manual

1. Copy `custom_components/carbu_fuel` into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.

## Configuration

1. Go to Settings -> Devices & Services -> Add Integration.
2. Search for **Carbu Fuel Prices**.
3. Select country and postal code.
4. Select town (if multiple are found).
5. Select fuel type.

You can add multiple entries (for example, different postal codes and/or fuel types).

## Entities

Each config entry creates:

- Station price sensors (one entity per station returned by carbu.com).
- One lowest-price summary sensor for that entry.
- One prediction sensor when prediction data is available for the selected fuel type.

## Development

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
uv sync
uv run ruff check custom_components tests
uv run pytest
```

Runtime dependencies are declared in `project.dependencies`, development tooling lives in
`dependency-groups.dev`, and the resolved environment is locked in `uv.lock`.

## License

MIT
