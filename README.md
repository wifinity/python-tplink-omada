# TP-Link Omada Python Client

A Python client library for the TP-Link Omada SDN controller API.

## Features

- **Client-Credentials Authentication**: Handles token acquisition via Omada local-controller OAuth flow.
- **Resource-Based API**: Exposes workflow-oriented resources from a single `OmadaClient` entry point.
- **Local Controller Support**: Uses explicit `base_url` + `omadac_id` configuration for controller-scoped requests.
- **Deterministic Spec Patching**: Applies repeatable OpenAPI fixups before model generation.
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

### Updating Sites

Use `client.sites.update(...)` to update an existing site by id. It accepts the
same field set used for site create flows:

- `name`
- `region`
- `scenario`
- `timezone` (mapped to API field `timeZone`)
- `device_username`
- `device_password`

```python
updated_site = client.sites.update(
    id="69e8b698f1c4806211fe52af",
    name="London HQ",
    region="United Kingdom",
    scenario="Work",
    timezone="Europe/London",
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
# ap_overview["result"]["wlanGroupName"] is added when wlanId can be resolved.

# Switch AP WLAN group by group id or exact group name
switch_result = client.aps.set_wlan_group_by_mac(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
    wlan_group="Corp",
)

# Get AP wired uplink detail by MAC
ap_wired_uplink = client.aps.get_wired_uplink_by_mac(
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
return a different result shape. When a `wlanId` (or legacy `wlan group id`) is present
and resolvable, it also adds `result.wlanGroupName`.
`client.aps.set_wlan_group_by_mac(...)` switches an AP to a target WLAN group through the
AP WLAN-group endpoint. `wlan_group` accepts either a WLAN group id or exact name.
`client.aps.get_wired_uplink_by_mac(...)` exposes the dedicated AP wired uplink endpoint.
For numeric wired-uplink fields, the client preserves raw values and also adds:
- `portTypeMeaning`
- `linkStatusMeaning`
- `linkSpeedMeaning`
- `duplexMeaning`
Unknown codes are preserved and mapped to deterministic fallback strings (for example
`Unknown linkSpeed: <code>`).
When `status` and `detailStatus` are present on DeviceInfo records, the client also adds
`statusMeaning` and `detailStatusMeaning` with decoded human-readable labels.
`client.aps.start_adopt(...)` and `client.aps.check_adopt(...)` are thin shortcut methods
that delegate to the canonical `client.devices` adopt operations.

### Switches

Use `client.switches` for switch onboarding workflows:

```python
# Retrieve all switches in a site (delegates to canonical devices.list with switch filter)
switches = client.switches.all(site_id="69e8b698f1c4806211fe52af")

# Get switch DeviceInfo by MAC
switch_device = client.switches.get_by_mac(site_id="69e8b698f1c4806211fe52af", mac="AA-BB-CC-DD-EE-FF")

# Get switch DeviceInfo by switch name
switch_device_by_name = client.switches.get_by_name(site_id="69e8b698f1c4806211fe52af", name="Core-SW-01")

# Create/register switch in a site (device key onboarding flow)
created_switch = client.switches.create(
    site_id="69e8b698f1c4806211fe52af",
    device_key="ZTP-DEVICE-KEY",
)

# Start switch adopt by MAC (switch facade shortcut to devices.start_adopt)
switch_adopt_result = client.switches.start_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Check switch adopt result by MAC (switch facade shortcut to devices.check_adopt)
switch_adopt_status = client.switches.check_adopt(
    site_id="69e8b698f1c4806211fe52af",
    mac="AA-BB-CC-DD-EE-FF",
)

# Delete/forget switch by MAC
forgotten = client.switches.delete(site_id="69e8b698f1c4806211fe52af", mac="AA-BB-CC-DD-EE-FF")
```

`client.switches` follows the same typed-facade-over-devices pattern as `client.aps`.
It filters list/lookup calls via `deviceType=\"switch\"` and delegates adopt operations
to the canonical `client.devices.start_adopt(...)` and `client.devices.check_adopt(...)`.

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

### Wi-Fi Networks

Use `client.wifi_networks` for SSID workflows scoped to a site and WLAN group. Omada always requires **`site_id`** and **`wlan_group`** (WLAN group id or name); there is no controller-wide SSID list.

**Order: list → get → filter → create → update → delete:**

```python
from omada_client import strip_ssid_detail_for_create

site_id = "69e8b698f1c4806211fe52af"
wlan_group = "Corp"

# List SSIDs under the WLAN group
wifi_networks = client.wifi_networks.all(site_id=site_id, wlan_group=wlan_group)

# Get one SSID by id or by exact broadcast name (JSON field `name`)
wifi_network = client.wifi_networks.get(site_id=site_id, wlan_group=wlan_group, name="GuestSSID")

# Filter list items (client-side); use `ssid=` as an alias for broadcast `name`
filtered = client.wifi_networks.filter(site_id=site_id, wlan_group=wlan_group, ssid="Guest")

# Create (see expanded examples below for security types)
created = client.wifi_networks.create(
    site_id=site_id,
    wlan_group=wlan_group,
    type="psk",
    name="GuestSSID",
    psk="StrongPassphrase123!",
)

# Update basic SSID fields: merges GET detail with `network_data` / kwargs, then PATCHes
# `.../update-basic-config` (Omada has no `PUT .../ssids/{id}`)
client.wifi_networks.update_basic_config(
    site_id=site_id,
    wlan_group=wlan_group,
    id="existing-ssid-id",
    network_data={"ssid": "UpdatedSSID"},  # `ssid` is an alias for Omada `name`
)

# Delete by id or name (Omada has no `deep=` delete flag)
delete_result = client.wifi_networks.delete(
    site_id=site_id,
    wlan_group=wlan_group,
    name="UpdatedSSID",
)
```

`filter(...)` only accepts documented criterion keys (unknown keys raise `ValueError`). When criteria are only broadcast-name selectors (`name` and/or matching `ssid`), the list call uses `searchKey` for a smaller response, then applies exact equality client-side.

`update_basic_config(...)` loads the current SSID detail, projects it to `UpdateSsidBasicConfigOpenApiVO`, merges overrides, and PATCHes. Use package helper `ssid_detail_to_basic_config_patch` if you build PATCH bodies yourself. Other SSID PATCH routes (rate limit, schedule, …) are not covered by this method.

Further examples (security types, VLAN, cloning):

```python
from omada_client import strip_ssid_detail_for_create

# Create WPA-Personal (pass name= or ssid= as the broadcast SSID; at least one required)
created_wifi_network = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="psk",
    name="GuestSSID",
    psk="StrongPassphrase123!",
)

# PPSK with RADIUS (security=5) — profile IDs as parameters (vlan= builds vlanSetting pool shape)
created_dpsk_network = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="dpsk",
    ssid="Resident",
    vlan=999,
    radius_profile_name="Home Networking Wi-Fi",
    nas_id="SITECODE",
)

# PPSK without RADIUS (security=4); pmf_mode defaults to 3 for ppsk_local/dpsk
created_ppsk_local = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="ppsk_local",
    ssid="Corporate",
    vlan=999,
    ppsk_profile_name="Services_PPSK_Profile",
)

# Multicast: flat PATCH fields (not nested under multiCast). Presets from docs/wlan_samples.
# filterMode bitmask: IGMP=1, mDNS=2, Others=4 (guest/signup samples use 15).
GUEST_MULTICAST = {
    "multiCastEnable": True,
    "ipv6CastEnable": True,
    "channelUtil": 100,
    "arpCastEnable": True,
    "filterEnable": True,
    "filterMode": 15,
}
SECURED_MULTICAST = {
    "multiCastEnable": True,
    "ipv6CastEnable": True,
    "channelUtil": 100,
    "arpCastEnable": True,
    "filterEnable": False,
}

# Open isolated (type=open-isolated sets guestNetEnable; vlan= builds standard vlan pool setting)
created_open_isolated = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="open-isolated",
    ssid="Guest",
    vlan=98,
    multicast_config=GUEST_MULTICAST,
    # Rate-limit is opt-in: pass rate_limit_profile_name to attach a site profile by name:
    # rate_limit_profile_name="Default",
)

# PPSK / DPSK with secured multicast (wpa.json / dpsk_radius.json parity)
created_ppsk_with_multicast = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="ppsk_local",
    ssid="Corporate",
    vlan=999,
    ppsk_profile_name="Services_PPSK_Profile",
    multicast_config=SECURED_MULTICAST,
)

# Rate control: caller supplies flat PATCH fields (not nested under rateControl).
# Field reference: docs/wlan_samples/*.json (rateControl key in samples is GET shape only).
RATE_CONTROL = {
    "rate2gCtrlEnable": True,
    "lowerDensity2g": 12,
    "higherDensity2g": 54,
    "rate5gCtrlEnable": True,
    "lowerDensity5g": 12,
    "higherDensity5g": 54,
}
created_open_isolated_with_rate = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="open-isolated",
    ssid="Guest",
    vlan=98,
    multicast_config=GUEST_MULTICAST,
    rate_control=RATE_CONTROL,
    rate_limit_profile_name="Default",  # POST then opt-in PATCHes: multicast, rate-control, rate-limit
)

# Standalone multicast PATCH on an existing SSID
client.wifi_networks.update_multicast_config(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    name="Guest",
    multicast_config=GUEST_MULTICAST,
)

# Standalone rate-control PATCH on an existing SSID
client.wifi_networks.update_rate_control(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    name="Guest",
    rate_control=RATE_CONTROL,
)

# Standalone rate-limit profile attachment (resolves the named site profile)
client.wifi_networks.update_rate_limit(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    name="Guest",
    rate_limit_profile_name="Default",  # exact Omada rate-limit profile name
)

# Omada vlanSetting (mutually exclusive with vlan= integer shortcut)
created_vlan_setting = client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="open",
    ssid="Signup",
    vlan_setting={
        "mode": 1,
        "customConfig": {"customMode": 1, "vlanPoolIds": "99"},
    },
)

# Clone from GET detail: strip read-only keys; match `type` to `security` in the trimmed payload
detail = client.wifi_networks.get(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    id="existing-ssid-id",
)
base = strip_ssid_detail_for_create(detail)
base.pop("name", None)  # broadcast name comes from create(ssid=...)
client.wifi_networks.create(
    site_id="69e8b698f1c4806211fe52af",
    wlan_group="Corp",
    type="psk",
    ssid="ClonedSSID",
    psk="NewPassphrase",
    network_data=base,
)
```

Supported `type` values (string `type` maps to Omada `security`):

- `open` (`security=0`; optional `guest_network=True/False` for `guestNetEnable`)
- `open-isolated` (`security=0`, `guestNetEnable=True`; open SSID with client isolation; wif-services schema name)
- `aaa` (`security=2`; requires `ent_setting`)
- `psk` (`security=3`; requires `psk` or `psk_setting`)
- `ppsk_local` (`security=4`; requires `psk` or `psk_setting` **and** `ppsk_setting`)
- `dpsk` (`security=5`; requires `ppsk_setting`, PPSK with RADIUS)

`hotspot20` is not supported in the SDK (raise a clear error); use raw `client.get`/`post` if you must drive HotspotV2 APIs.

`network_data` must not include `name`; set the broadcast SSID via `ssid` and/or `name`.

`create()` is not atomic: it POSTs the SSID, then runs the opt-in `multicast_config` / `rate_control` / `rate_limit_profile_name` PATCHes. If a PATCH fails after the POST, `create()` raises `WiFiNetworkPartiallyConfiguredError` — the SSID already exists, and the exception carries `ssid_id`, `failed_step`, and `completed_steps` so you can retry the failed step or delete the SSID.

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

### OLT / ONU optics (GPON)

Use `client.olts` to query ONU optical telemetry from an upstream OLT. The Omada API requires an ONU **`key`**
identifier for detail telemetry; this SDK provides a MAC-based convenience method that resolves the key via the
ONU list endpoint.

```python
onu_detail = client.olts.get_onu_detail_by_mac(
    site_id="69e8b698f1c4806211fe52af",
    olt_mac="9C-53-22-71-A3-54",
    pon_port="GPON 1/1/1",
    onu_mac="F0-09-0D-E4-09-83",
)

# Raw Omada payload, for example:
# onu_detail["result"]["onuOpticalLinkInformation"]["receivedOpticalPower"]
# onu_detail["result"]["onuOpticalLinkInformation"]["transmittedOpticalPower"]
```

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