# TP-Link Omada Python Client

A Python client library for the TP-Link Omada SDN controller API.

## Features

- **Client-Credentials Authentication**: Handles token acquisition via Omada local-controller OAuth flow.
- **Resource-Based API**: Exposes workflow-oriented resources from a single `OmadaClient` entry point.
- **Local Controller Support**: Uses explicit `base_url` + `omadac_id` configuration for controller-scoped requests.
- **Deterministic Spec Patching**: Applies repeatable OpenAPI fixups before model generation.
- **Developer Workflow Automation**: Provides make targets for formatting, linting, spec fix/validate, generation, and tests.
- **Internal Generated Models**: Keeps generated schema models internal to preserve a stable public API.

## Installation

```bash
uv venv
uv sync --extra dev
```

## Quick Start

```python
from omada_client import OmadaClient

client = OmadaClient(
    base_url="https://controller.example",
    omadac_id="your-omadac-id",
    client_id="your-client-id",
    client_secret="your-client-secret",
)

site = client.sites.create(
    name="Main Site",
    device_username="omada-admin",
    device_password="StrongPassword!123",
)
print(site)
```

## Usage

### Named Parameters Policy

Public resource methods are keyword-only and should be called with named arguments.
This applies to `client.sites`, `client.devices`, `client.aps`, `client.wifi_networks`, `client.wlan_groups`, and `client.ap_groups`.

### Client Initialization

```python
from omada_client import OmadaClient

client = OmadaClient(
    base_url="https://controller.example",
    omadac_id="your-omadac-id",
    client_id="your-client-id",
    client_secret="your-client-secret",
)
```

### Local Controller Mode

Local-controller mode requires:

- `base_url` pointing to the controller host.
- `omadac_id` matching the controller identifier.
- Token exchange through `POST /openapi/authorize/token` using query `grant_type=client_credentials`.
- JSON token payload fields: `omadacId`, `client_id`, `client_secret`.
- API authentication header format: `Authorization: AccessToken=<token>`.

### Creating Sites

`client.sites.create()` now includes defaults for Omada-required fields:

- `region` defaults to `"United Kingdom"`
- `scenario` defaults to `"Dormitory"`
- `time_zone` defaults to `"UTC"` (mapped to API field `timeZone`)

Device credentials are exposed as explicit parameters:

- `device_username`
- `device_password`

Both must be provided together unless you pass a raw `deviceAccountSetting` object in `**kwargs`.
`region` is validated as a full country name (for example, `United Kingdom`), and ISO
codes like `GB`/`GBR` are rejected with a clear error.

```python
site = client.sites.create(
    name="Main Site",
    device_username="omada-admin",
    device_password="StrongPassword!123",
)

site_custom = client.sites.create(
    name="London HQ",
    region="United Kingdom",
    scenario="Work",
    time_zone="Europe/London",
    device_username="site-admin",
    device_password="AnotherStrongPassword!123",
)
```

### Reading Sites

Use `client.sites.all()` to fetch all sites and `client.sites.get(...)` to resolve one site.

```python
all_sites = client.sites.all()
print(all_sites)

site_by_id = client.sites.get(id="69e8b698f1c4806211fe52af")
print(site_by_id)

site_by_name = client.sites.get(name="johantest")
print(site_by_name)
```

`client.sites.get(name=...)` resolves the matching `siteId` and then fetches the canonical
`/sites/{siteId}` entity, so it returns the same detail shape as `client.sites.get(id=...)`.

#### Site query examples

```python
# First page (defaults are page=1, pageSize=1000)
sites_page_1 = client.sites.all()

# Explicit paging
sites_page_2 = client.sites.all(params={"page": 2, "pageSize": 50})

# Server-side search with paging override
filtered_sites = client.sites.all(
    params={"searchKey": "johan", "page": 1, "pageSize": 100}
)

# Canonical detail by id
site_detail = client.sites.get(id="69e8b698f1c4806211fe52af")

# Same canonical detail by name lookup
site_detail_by_name = client.sites.get(name="johantest")
```

### Access Points

Use `client.aps` for AP-focused workflows:

```python
# Retrieve all APs in a site (delegates to canonical devices.list with AP filter)
aps = client.aps.all(site_id="69e8b698f1c4806211fe52af")

# Get AP DeviceInfo by MAC (same item shape as /devices list data entries)
ap_device = client.aps.get_by_mac(site_id="69e8b698f1c4806211fe52af", mac="AA-BB-CC-DD-EE-FF")

# Get AP DeviceInfo by AP name
ap_device_by_name = client.aps.get_by_name(site_id="69e8b698f1c4806211fe52af", name="Lobby-AP-01")

# Get AP overview payload by MAC (ApOverviewInfo-style endpoint)
ap_overview = client.aps.get_overview_by_mac(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Delete/forget AP by MAC
ap = client.aps.delete(site_id="69e8b698f1c4806211fe52af", mac="AA-BB-CC-DD-EE-FF")

# Create/register AP in a site (device key onboarding flow)
created_ap = client.aps.create(site_id="69e8b698f1c4806211fe52af", device_key="ZTP-DEVICE-KEY")

# Start AP adopt by MAC (AP facade shortcut to devices.start_adopt)
ap_adopt_result = client.aps.start_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Check AP adopt result by MAC (AP facade shortcut to devices.check_adopt)
ap_adopt_status = client.aps.check_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Update AP general config by MAC
ap_update = client.aps.update(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
    data={"name": "hostname"},
)
```

`client.aps.get_by_mac(...)` and `client.aps.get_by_name(...)` return DeviceInfo-style
records resolved from the AP-filtered device list flow.
When AP MAC lookup misses, `client.aps.get_by_mac(...)` raises `DeviceNotFoundError`.
`client.aps.get_overview_by_mac(...)` exposes the dedicated AP overview endpoint and can
return a different result shape.
When `status` and `detailStatus` are present on DeviceInfo records, the client also adds
`statusMeaning` and `detailStatusMeaning` with decoded human-readable labels.
`client.aps.start_adopt(...)` and `client.aps.check_adopt(...)` are thin shortcut methods
that delegate to the canonical `client.devices` adopt operations.

### Wireless Network Groups

Use `client.wlan_groups` for WLAN group workflows:

```python
# List WLAN groups in a site
wlan_groups = client.wlan_groups.all(site_id="69e8b698f1c4806211fe52af")

# Create a WLAN group
created_group = client.wlan_groups.create(
    site_id="69e8b698f1c4806211fe52af",
    name="Corp",
)

# Resolve a WLAN group by name
wlan_group = client.wlan_groups.get(
    site_id="69e8b698f1c4806211fe52af",
    name="Corp",
)

# Delete a WLAN group by name
delete_result = client.wlan_groups.delete(
    site_id="69e8b698f1c4806211fe52af",
    name="Corp",
)
```

`client.wlan_groups.get(...)` and `client.wlan_groups.delete(...)` require exactly one
selector (`id` or `name`). Name-based operations use exact-name matching and raise
`WLANGroupNotFoundError` for missing groups, and `ValueError` for ambiguous matches.
`client.wlan_groups.create(...)` accepts `name` directly and defaults `clone=False`
unless explicitly overridden in `group_data`.

### Devices

```python
# Start adopt by MAC using named parameters
adopt_result = client.devices.start_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Optionally provide device login credentials for adoption
adopt_result = client.devices.start_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
    username="admin",
    password="device-password",
)

# Check latest adopt result by MAC and get decoded meanings
adopt_status = client.devices.check_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)
# adopt_status["result"]["adoptErrorMeaning"]
# adopt_status["result"]["adoptFailedTypeMeaning"]
```

`start_adopt` always sends a JSON body with `username` and `password`. When not
provided, both fields default to `admin`.

`check_adopt` calls `/adopt-result` and preserves the raw fields (`adoptErrorCode`,
`adoptFailedType`) while adding `adoptErrorMeaning` and `adoptFailedTypeMeaning`
derived from the Omada OpenAPI `AdoptResult` descriptions.

MAC inputs are validated and normalized with the `macaddress` package. Public methods
that accept `mac` support common EUI-48 forms (for example `AA:BB:CC:DD:EE:FF`,
`AA-BB-CC-DD-EE-FF`, `AABBCCDDEEFF`, and `aabb.ccdd.eeff`) and always send
`AA-BB-CC-DD-EE-FF` to the Omada API.

For DeviceInfo-shaped lookup responses (for example `client.devices.get_by_mac(...)` and
`client.aps.get_by_mac(...)`), when numeric `status`/`detailStatus` are present, the
response also includes:
- `statusMeaning`
- `detailStatusMeaning`

Unknown numeric codes are preserved and get deterministic fallback strings:
- `Unknown status: <code>`
- `Unknown detailStatus: <code>`

### Device Resource Architecture

`client.devices` is the canonical shared endpoint/action layer for device CRUD-like operations.
Typed resources such as `client.aps` are thin facades that reuse `client.devices` with
device-type-specific defaults and options. Future resources (for example switches) should
follow the same facade-over-devices pattern.

## OpenAPI Spec Issues and Mitigation

The published Omada OpenAPI spec contains recurring defects that make direct generation brittle for a stable SDK:

- Missing path parameters in path templates.
- Invalid or unresolved schema references.
- Content-type mismatches (JSON payloads exposed with misleading media types).
- Unstable or misleading operation IDs.

This repository follows a deterministic patching approach inspired by [omada-go-sdk](https://github.com/Tohaker/omada-go-sdk):

- Fetch upstream spec into `spec/raw/all.json`.
- Normalize and patch into `spec/fixed/all-fixed.json`.
- Apply issue-focused overlays in `spec/patches/`.
- Validate fixed spec before model generation.

## Deterministic Developer Workflow

```bash
make venv
make format-check
make lint
make typecheck
make spec-fetch
make spec-fix
make spec-validate
make generate-models
make tests
```

## Development

### Generated Artifacts

Generated models are internal (`omada_client.generated.models`) and are not part of the public API in the initial release.
