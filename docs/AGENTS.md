# Agent guide — python-tplink-omada

## What this repo is

Python client for the TP-Link Omada OpenAPI. Dict-first resource wrappers cover
sites, devices, APs, switches, WLAN groups, Wi-Fi SSIDs, AP groups, LAN networks,
RADIUS profiles, OLTs, and site services. Generated models stay internal.
Does **not** own workflows or inventory integration.

## Package layout (`omada_client/`)

| Path | Purpose |
|------|---------|
| `omada_client/client.py` | `OmadaClient` — entry point and resource sub-clients |
| `omada_client/auth.py` | OAuth2 client credentials (`/openapi/authorize/token`) |
| `omada_client/config.py` | Client configuration |
| `omada_client/mac.py` | MAC validation/normalization (`AA-BB-CC-DD-EE-FF`) |
| `omada_client/exceptions.py` | `WLANGroupNotFoundError`, `DeviceNotFoundError`, `LanNetworkNotFoundError`, etc. |
| `omada_client/resources/` | Sites, devices, APs, switches, WLAN groups, Wi-Fi networks, AP groups, LAN networks, RADIUS profiles, OLTs, site services |
| `omada_client/generated/models/` | Internal OpenAPI-generated models (not public API) |
| `omada_client/wifi_payload_utils.py` | SSID create/update payload helpers |

Repo root: `tests/`, `docs/`, `spec/`, `tools/`, `Makefile`, `pyproject.toml`.

## Conventions

- **Public API is dict-first** for ergonomics; generated models remain internal.
- **Public resource methods are keyword-only** (`def method(self, *, ...)`).
- **MAC parameter name:** `mac` — validated/normalized to uppercase hyphen EUI-48.
- **Site defaults** on create/update: `region="United Kingdom"`, `scenario="Dormitory"`, `time_zone`/`timezone="UTC"`.
- **Region input:** full country name via `pycountry`; ISO codes rejected.
- **Spec workflow:** fetch → patch (`tools/fix_spec.py`) → validate → `make generate-models`.

## Where to look

- **ADR (single file):** [adr.md](adr.md) — numbered decisions (named params, MAC policy, Wi-Fi types, etc.)
- **Index:** [INDEX.md](INDEX.md)
- **Memory:** [.agents/memory/python-tplink-omada-repository-memory.md](../.agents/memory/python-tplink-omada-repository-memory.md)

## Starting a new task

1. Read `.agents/memory/python-tplink-omada-repository-memory.md`.
2. Read relevant section in `docs/adr.md` for the change area.
3. Run `make tests` before opening a PR.

## Testing

- Full suite: `make tests`; spec pipeline: `make spec-fix`, `make spec-validate`, `make generate-models`.
- Tests in `tests/` with `pytest`; use `pytest-httpx` for HTTP behavior.
