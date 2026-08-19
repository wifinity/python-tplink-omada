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

Each resource is reached from a single `OmadaClient` instance via a named accessor
(for example `client.sites`, `client.aps`). Sections below are grouped by area:
**sites**, **devices**, **wireless**, **networking**, and **optics**.

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

### Sites

`client.sites` manages Omada sites. Create and update include defaults for
Omada-required fields:

- `region` defaults to `"United Kingdom"` — validated as a full country name, so
  ISO codes like `GB`/`GBR` are rejected with a clear error.
- `scenario` defaults to `"Dormitory"`.
- `time_zone` defaults to `"UTC"` (mapped to API field `timeZone`).

Device credentials are explicit parameters (`device_username`, `device_password`)
and must be provided together unless you pass a raw `deviceAccountSetting` object
in `**kwargs`.

```python
# Create a site (with defaults, then with explicit fields)
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

# Update an existing site by id (same field set; `timezone` maps to `timeZone`)
updated_site = client.sites.update(
    id="your-site-id",
    name="London HQ",
    region="United Kingdom",
    scenario="Work",
    timezone="Europe/London",
    device_username="site-admin",
    device_password="AnotherStrongPassword!123",
)

# List all sites, or resolve one by id or name
all_sites = client.sites.all()
site_by_id = client.sites.get(id="your-site-id")
site_by_name = client.sites.get(name="johantest")

# Paging (defaults are page=1, pageSize=1000) and server-side search
sites_page_2 = client.sites.all(params={"page": 2, "pageSize": 50})
filtered_sites = client.sites.all(params={"searchKey": "johan", "page": 1, "pageSize": 100})
```

`client.sites.get(name=...)` resolves the matching `siteId` and then fetches the
canonical `/sites/{siteId}` entity, so it returns the same detail shape as
`client.sites.get(id=...)`.

### Site Services

`client.site_services` manages site-level service settings (currently SNMP).

```python
# Read SNMP settings for a site
snmp = client.site_services.get_snmp(site_id="your-site-id")

# Update SNMP settings
client.site_services.update_snmp(
    site_id="your-site-id",
    snmpv1v2c_enable=True,
    snmpv3_enable=False,
    community_string="public",
)
```

`update_snmp` requires `snmpv1v2c_enable` and `snmpv3_enable`; `community_string`,
`username`, and `password` are optional and only sent when provided.

### Devices

`client.devices` is the canonical shared endpoint/action layer for device
CRUD-like operations. Typed resources such as `client.aps` and `client.switches`
are thin facades that reuse `client.devices` with device-type-specific defaults;
new device resources should follow the same facade-over-devices pattern.

```python
# Start adopt by MAC (optionally with device login credentials)
adopt_result = client.devices.start_adopt(
    site_id="your-site-id",
    mac="AA-BB-CC-DD-EE-FF",
    username="admin",             # optional; defaults to "admin"
    password="device-password",   # optional; defaults to "admin"
)

# Check the latest adopt result by MAC (adds decoded meanings)
adopt_status = client.devices.check_adopt(
    site_id="your-site-id",
    mac="AA-BB-CC-DD-EE-FF",
)
# adopt_status["result"]["adoptErrorMeaning"]
# adopt_status["result"]["adoptFailedTypeMeaning"]
```

`start_adopt` always sends a JSON body with `username` and `password` (both
default to `admin`). `check_adopt` calls `/adopt-result`, preserves the raw
`adoptErrorCode`/`adoptFailedType` fields, and adds `adoptErrorMeaning`/
`adoptFailedTypeMeaning` derived from the Omada `AdoptResult` descriptions.

MAC inputs are validated and normalized with the `macaddress` package. Public
methods that accept `mac` support common EUI-48 forms (for example
`AA:BB:CC:DD:EE:FF`, `AA-BB-CC-DD-EE-FF`, `AABBCCDDEEFF`, and `aabb.ccdd.eeff`)
and always send `AA-BB-CC-DD-EE-FF` to the API. For DeviceInfo-shaped responses
(for example `client.devices.get_by_mac(...)`), when numeric `status`/`detailStatus`
are present the response also includes `statusMeaning` and `detailStatusMeaning`;
unknown codes are preserved and get deterministic fallbacks like
`Unknown status: <code>`.

### Access Points

`client.aps` provides AP-focused workflows as a typed facade over `client.devices`
(filtering the device list to APs).

```python
# List all APs in a site
aps = client.aps.all(site_id="your-site-id")

# Look up AP DeviceInfo by MAC, name, or serial number
ap_device = client.aps.get_by_mac(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
ap_device_by_name = client.aps.get_by_name(site_id="your-site-id", name="Lobby-AP-01")
ap_device_by_serial = client.aps.get_by_serial(site_id="your-site-id", serial="your-device-serial")

# AP overview payload by MAC (adds result.wlanGroupName when wlanId resolves)
ap_overview = client.aps.get_overview_by_mac(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")

# Wired uplink detail by MAC (adds decoded *Meaning fields)
ap_wired_uplink = client.aps.get_wired_uplink_by_mac(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")

# Switch an AP to a target WLAN group (by group id or exact name)
switch_result = client.aps.set_wlan_group_by_mac(
    site_id="your-site-id",
    mac="AA-BB-CC-DD-EE-FF",
    wlan_group="Corp",
)

# --- AP ethernet ports (daisy-chain support) ---
# Per-port capability flags (gate writes on these); string port ids ("ETH0"...)
ports = client.aps.get_ports(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
# Current per-port VLAN associations (native/tagged/untagged)
port_vlans = client.aps.get_port_vlans(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")

# Configure a daisy-chain trunk on ETH0: management untagged on VLAN 1 + services tagged.
# By-Network path (custom=False). For VLAN-1-untagged management, OMIT
# localVlanNetworkId (an explicit VLAN-1 native is rejected by the controller).
vlan_map = client.lan_networks.vlan_id_to_network_id(site_id="your-site-id")
client.aps.update_ports(
    site_id="your-site-id",
    mac="AA-BB-CC-DD-EE-FF",
    ports=["ETH0"],
    settings={
        "status": True,
        "poeOutEnable": True,          # power the downstream AP
        "custom": False,               # By Network
        "localVlanEnable": True,       # native left unset -> default VLAN 1, untagged
        "taggedNetworkId": [vlan_map[98], vlan_map[99]],
        "untaggedNetworkId": [],
    },
)

# Register, update, adopt, and delete
created_ap = client.aps.create(site_id="your-site-id", device_key="ZTP-DEVICE-KEY")
client.aps.update(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF", data={"name": "hostname"})
client.aps.start_adopt(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
client.aps.check_adopt(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
client.aps.delete(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
```

`get_by_mac`/`get_by_name`/`get_by_serial` return DeviceInfo-style records
resolved from the AP-filtered device list; `get_by_mac`/`get_by_serial` raise
`DeviceNotFoundError` on a miss (`get_by_name` raises `ValueError`, since name
collisions are possible). `get_by_serial` matches on the `sn` field and always
scans the full AP-filtered device list client-side, since `sn` is not a
supported `searchKey` field on the Omada API.
`get_overview_by_mac` uses the dedicated AP overview endpoint (a different result
shape) and adds `result.wlanGroupName` when a `wlanId` (or legacy WLAN group id)
is present and resolvable via `wlan_groups.get` — the id lookup scans the WLAN
group list, as there is no per-group GET by id. `get_wired_uplink_by_mac`
preserves raw numeric fields and adds `portTypeMeaning`, `linkStatusMeaning`,
`linkSpeedMeaning`, and `duplexMeaning` (unknown codes map to deterministic
fallbacks like `Unknown linkSpeed: <code>`). `start_adopt`/`check_adopt` are thin
shortcuts that delegate to the canonical `client.devices` adopt operations.

`get_ports`/`get_port_vlans`/`update_ports` wrap the AP ethernet-port endpoints
(the batch `POST /aps/ports/capability` + `POST /aps/ports/config`, which work
across single- and multi-port AP models — the single-port `GET /ports` /
`PATCH /ports/{port}` error on multi-port models). `get_ports` returns capability
flags only (not live state); gate writes on `supportVlanTagged` — tagged VLANs
are silently ignored on ports that do not support them. `update_ports` passes
`settings` through verbatim (dict-first). Note the controller **rejects VLAN 1 as
an explicit native** (error `-39348`): for VLAN-1-untagged management, omit
`localVlanNetworkId` as shown above. The 8-VLAN hardware limit is not enforced
here — that is the caller's responsibility.

### AP Groups

`client.ap_groups` creates AP groups in a site. The `group_data` body is passed
through to the Omada API unchanged.

```python
created_group = client.ap_groups.create(
    site_id="your-site-id",
    group_data={"name": "Lobby APs"},
)
```

### Switches

`client.switches` provides switch onboarding and configuration workflows as a
typed facade over `client.devices` (filtering via `deviceType="switch"` and
delegating adopt operations to `client.devices.start_adopt(...)` /
`client.devices.check_adopt(...)`).

```python
# List all switches, or look up one by MAC, name, or serial number
switches = client.switches.all(site_id="your-site-id")
switch_device = client.switches.get_by_mac(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
switch_device_by_name = client.switches.get_by_name(site_id="your-site-id", name="Core-SW-01")
switch_device_by_serial = client.switches.get_by_serial(site_id="your-site-id", serial="your-device-serial")

# Register, adopt, and delete
created_switch = client.switches.create(site_id="your-site-id", device_key="ZTP-DEVICE-KEY")
client.switches.start_adopt(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
client.switches.check_adopt(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
client.switches.delete(site_id="your-site-id", mac="AA-BB-CC-DD-EE-FF")
```

`get_by_mac`/`get_by_name`/`get_by_serial` share the same lookup contract as
the AP resource above: DeviceInfo-style records, `get_by_mac`/`get_by_serial`
raise `DeviceNotFoundError` on a miss, and `get_by_serial` matches on `sn` by
scanning the full switch-filtered device list client-side (no `searchKey`
support for serial numbers).

**LAN port profiles** are managed dict-first (the caller builds the
`LanProfileSettingOpenApiVO` body; the SDK passes it through unchanged):

```python
profile = {
    "name": "role-uplink",
    "bandWidthCtrlType": 0,
    "dot1x": 0,
    "lldpMedEnable": True,
    "loopbackDetectEnable": True,
    "poe": 2,
    "portIsolationEnable": False,
    "spanningTreeEnable": True,
}

# Create -> {"id": "<newProfileId>"}
created = client.switches.create_port_profile(site_id="your-site-id", profile=profile)

# Update by explicit id, or resolve the id from profile["name"] when omitted
client.switches.update_port_profile(site_id="your-site-id", profile=profile, profile_id=created["id"])
client.switches.update_port_profile(site_id="your-site-id", profile=profile)

# Create-or-update by name -> (profile_dict, created: bool)
result, was_created = client.switches.upsert_port_profile(site_id="your-site-id", profile=profile)

# Delete by id or by name (exactly one)
client.switches.delete_port_profile(site_id="your-site-id", name="role-uplink")
```

**Per-port config** is applied one port at a time with `update_switch_port`. The
`settings` dict is an `OswPortSettingVO` passed through unchanged (no validation,
translation, or defaulting). VLAN fields take Omada LAN network IDs — resolve VLAN
numbers first via `client.lan_networks.vlan_id_to_network_id`. Admin enable/disable
is managed via the port profile (`set_port_profiles`), not the `disable` field:

```python
net_ids = client.lan_networks.vlan_id_to_network_id(site_id="your-site-id")

client.switches.update_switch_port(
    site_id="your-site-id",
    switch_mac="AA-BB-CC-DD-EE-FF",
    port=5,
    settings={
        "name": "AP-uplink",
        "nativeNetworkId": net_ids[1],
        "tagNetworkIds": [net_ids[10], net_ids[20]],
        "networkTagsSetting": 2,      # 0 Allow All, 1 Block All, 2 Custom
        "dhcpSnoopEnable": True,      # DHCP-snooping trust
        "profileOverrideEnable": True,
    },
)
```

**LLDP neighbors** are read via `get_lldp_neighbors`, returning each neighbor
as an `OswLldpNeighborVO` dict. `portId` matches the switch's own `port`
number from `get_ports`. Returns `[]` when the switch has no neighbors, is
not yet adopted, or the MAC is unrecognized — this endpoint gives no
distinguishable "not found" signal. Note that `systemName`/`neighborPortId`
reflect whatever the *neighboring device's own firmware* broadcasts, not
necessarily its configured hostname or a real port name/index — single-port
devices like APs commonly report their own MAC as `neighborPortId`. Prefer
`deviceId` (when present) over `systemName` for a reliable MAC/chassis-id
match:

```python
neighbors = client.switches.get_lldp_neighbors(
    site_id="your-site-id",
    switch_mac="AA-BB-CC-DD-EE-FF",
)
# neighbors: [{"portId": 7, "deviceId": "11-22-33-44-55-66", "systemName": "EAP725-Wall",
#              "neighborPortId": "11-22-33-44-55-66", "ttl": 120, "capabilities": "Router,Bridge"}, ...]
```

### Switch 802.1X

`client.switch_dot1x` manages switch global (system) 802.1X settings, which Omada
scopes as a single **per-site** resource (not per switch). Bodies are dict-first
(passed through unchanged), so the caller owns building and reconciling them via
read-modify-write.

```python
# Read the site's current switch 802.1X setting (Dot1xSwitchResOpenApiVO; {} if never configured)
current = client.switch_dot1x.get(site_id="your-site-id")

# Resolve the RADIUS profile id referenced by radiusProfileId
profile = client.radius_profiles.get(site_id="your-site-id", name="My RADIUS Profile")

# Update (Dot1xSwitchOpenApiVO body)
client.switch_dot1x.update(
    site_id="your-site-id",
    settings={
        "enable": True,
        "authMode": 1,        # 0 PAP, 1 EAP
        "authType": 0,        # 0 port-based, 1 mac-based
        "mab": False,
        "macFormat": 0,
        "radiusProfileId": profile["radiusProfileId"],
        "vlanAssign": False,
    },
)
```

`get` returns the current setting with `result` unwrapped and does **not** echo the
per-port `switches` array. `update` requires `authMode`, `authType`, `enable`,
`mab`, `macFormat`, `radiusProfileId`, and `vlanAssign`; optional keys include
`guestVlan`, `nasId`, and the per-port `switches` array (`dot1xPorts`/`mabPorts`
keyed by switch `mac`). Read-modify-write so unmanaged required fields and the
per-port array are preserved.

Because `get` omits the per-port state, use `candidates` to read current per-port
802.1X/MAB before reconciling:

```python
# Per-switch, per-port 802.1X/MAB state (the read side of the `switches` array)
for sw in client.switch_dot1x.candidates(site_id="your-site-id"):
    for p in sw["ports"]:
        # p: {"port", "dot1xEnable", "mabEnable", "authType"}  authType 2 == MAB only
        ...
```

A port must appear in **only one** of `dot1xPorts`/`mabPorts` — the "Both" mode
(`authType 3`) is rejected by the Open API.

### Wireless Network Groups

`client.wlan_groups` manages WLAN groups within a site.

```python
wlan_groups = client.wlan_groups.all(site_id="your-site-id")
created_group = client.wlan_groups.create(site_id="your-site-id", name="Corp")
wlan_group = client.wlan_groups.get(site_id="your-site-id", name="Corp")
delete_result = client.wlan_groups.delete(site_id="your-site-id", name="Corp")
```

`get` and `delete` require exactly one selector (`id` or `name`). Name-based
operations use exact-name matching and raise `WLANGroupNotFoundError` for missing
groups and `ValueError` for ambiguous matches. `create` accepts `name` directly
and defaults `clone=False` unless overridden in `group_data`.

### Wi-Fi Networks

`client.wifi_networks` manages SSIDs scoped to a site and WLAN group. Omada always
requires **`site_id`** and **`wlan_group`** (WLAN group id or name); there is no
controller-wide SSID list.

```python
from omada_client import strip_ssid_detail_for_create

site_id = "your-site-id"
wlan_group = "Corp"

# List, get (by id or exact broadcast name), and client-side filter
wifi_networks = client.wifi_networks.all(site_id=site_id, wlan_group=wlan_group)
wifi_network = client.wifi_networks.get(site_id=site_id, wlan_group=wlan_group, name="GuestSSID")
filtered = client.wifi_networks.filter(site_id=site_id, wlan_group=wlan_group, ssid="Guest")  # `ssid` aliases `name`

# Create (see security types and further examples below)
created = client.wifi_networks.create(
    site_id=site_id, wlan_group=wlan_group, type="psk", name="GuestSSID", psk="StrongPassphrase123!",
)

# Update basic SSID fields (PATCHes .../update-basic-config; Omada has no PUT .../ssids/{id})
client.wifi_networks.update_basic_config(
    site_id=site_id, wlan_group=wlan_group, id="existing-ssid-id",
    network_data={"ssid": "UpdatedSSID"},  # `ssid` aliases Omada `name`
)

# Delete by id or name (Omada has no `deep=` delete flag)
client.wifi_networks.delete(site_id=site_id, wlan_group=wlan_group, name="UpdatedSSID")
```

`filter` only accepts documented criterion keys (unknown keys raise `ValueError`).
When criteria are only broadcast-name selectors (`name` and/or matching `ssid`),
the list call uses `searchKey` for a smaller response, then applies exact equality
client-side. `update_basic_config` loads the current SSID detail, projects it to
`UpdateSsidBasicConfigOpenApiVO`, merges overrides, and PATCHes (use the package
helper `ssid_detail_to_basic_config_patch` if you build PATCH bodies yourself);
other PATCH routes (rate limit, schedule, …) are not covered by this method.

**Supported `type` values** (string `type` maps to Omada `security`):

- `open` (`security=0`; optional `guest_network=True/False` for `guestNetEnable`)
- `open-isolated` (`security=0`, `guestNetEnable=True`; open SSID with client isolation)
- `aaa` (`security=2`; requires `ent_setting`)
- `psk` (`security=3`; requires `psk` or `psk_setting`)
- `ppsk_local` (`security=4`; requires `psk` or `psk_setting` **and** `ppsk_setting`; alias `ppsk-local`)
- `dpsk` (`security=5`; requires `ppsk_setting`, PPSK with RADIUS)

`hotspot20` is not supported in the SDK (raises a clear error); use raw
`client.get`/`post` if you must drive HotspotV2 APIs. `network_data` must not
include `name`; set the broadcast SSID via `ssid` and/or `name`.

`create()` is **not atomic**: it POSTs the SSID, then runs the opt-in
`multicast_config` / `rate_control` / `rate_limit_profile_name` PATCHes. If a PATCH
fails after the POST, `create()` raises `WiFiNetworkPartiallyConfiguredError` — the
SSID already exists, and the exception carries `ssid_id`, `failed_step`, and
`completed_steps` so you can retry the failed step or delete the SSID.

**Further examples — security types, VLAN, multicast, rate control, and cloning:**

```python
from omada_client import strip_ssid_detail_for_create

# WPA-Personal (security=3) — shared passphrase
created_wifi_network = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="psk",
    name="GuestSSID",
    psk="StrongPassphrase123!",
    vlan=102,
    # pmf_mode defaults to 3 for psk (wpa_basic.json); pass pmf_mode=2 for PMF capable
)

# PPSK with RADIUS (security=5) — profile IDs as parameters (vlan= builds vlanSetting pool shape)
created_dpsk_network = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="dpsk",
    ssid="Resident",
    vlan=999,
    radius_profile_name="My RADIUS Profile",
    nas_id="SITECODE",
)

# PPSK without RADIUS (security=4); pmf_mode defaults to 3 for ppsk_local/dpsk
created_ppsk_local = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="ppsk_local",
    ssid="Corporate",
    vlan=999,
    ppsk_profile_name="My_PPSK_Profile",
)

# Multicast: flat PATCH fields (not nested under multiCast). Caller owns preset dicts.
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

# Rate control: caller supplies flat PATCH fields (the rateControl key in GET detail is not the PATCH body).
RATE_CONTROL = {
    "rate2gCtrlEnable": True,
    "lowerDensity2g": 12,
    "higherDensity2g": 54,
    "rate5gCtrlEnable": True,
    "lowerDensity5g": 12,
    "higherDensity5g": 54,
}

# Open isolated (type=open-isolated sets guestNetEnable; vlan= builds standard vlan pool setting)
# POST then opt-in PATCHes: multicast, rate-control, rate-limit
created_open_isolated_with_rate = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="open-isolated",
    ssid="Guest",
    vlan=98,
    multicast_config=GUEST_MULTICAST,
    rate_control=RATE_CONTROL,
    rate_limit_profile_name="Default",  # attach a site rate-limit profile by exact name
)

# PPSK / DPSK with secured multicast (wpa.json / dpsk_radius.json parity)
created_ppsk_with_multicast = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="ppsk_local",
    ssid="Corporate",
    vlan=999,
    ppsk_profile_name="My_PPSK_Profile",
    multicast_config=SECURED_MULTICAST,
)

# Omada vlanSetting (mutually exclusive with vlan= integer shortcut)
created_vlan_setting = client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="open",
    ssid="Signup",
    vlan_setting={
        "mode": 1,
        "customConfig": {"customMode": 1, "vlanPoolIds": "99"},
    },
)

# Standalone PATCHes on an existing SSID
client.wifi_networks.update_multicast_config(
    site_id="your-site-id", wlan_group="Corp", name="Guest", multicast_config=GUEST_MULTICAST,
)
client.wifi_networks.update_rate_control(
    site_id="your-site-id", wlan_group="Corp", name="Guest", rate_control=RATE_CONTROL,
)
client.wifi_networks.update_rate_limit(
    site_id="your-site-id", wlan_group="Corp", name="Guest",
    rate_limit_profile_name="Default",  # exact Omada rate-limit profile name
)

# Clone from GET detail: strip read-only keys; match `type` to `security` in the trimmed payload
detail = client.wifi_networks.get(
    site_id="your-site-id", wlan_group="Corp", id="existing-ssid-id",
)
base = strip_ssid_detail_for_create(detail)
base.pop("name", None)  # broadcast name comes from create(ssid=...)
client.wifi_networks.create(
    site_id="your-site-id",
    wlan_group="Corp",
    type="psk",
    ssid="ClonedSSID",
    psk="NewPassphrase",
    network_data=base,
)
```

### LAN Networks

`client.lan_networks` manages 802.1Q VLAN definitions (Omada "LAN networks") for a
site.

```python
# List all LAN networks on a site
networks = client.lan_networks.all(site_id="your-site-id")

# Get a network by Omada network ID string or VLAN integer
network = client.lan_networks.get(site_id="your-site-id", network_id="your-network-id")
network = client.lan_networks.get(site_id="your-site-id", vlan_id=98)

# Create a VLAN-type LAN network (DHCP server disabled by default)
created = client.lan_networks.create(
    site_id="your-site-id",
    name="guest",
    vlan_id=98,
)

# Update — reads current state then merges; pass only the fields you want to change
client.lan_networks.update(
    site_id="your-site-id",
    vlan_id=98,
    name="guest-renamed",
)

# Delete a network
client.lan_networks.delete(site_id="your-site-id", vlan_id=98)

# Build a {vlan_id: network_id} lookup — useful when resolving VLAN integers to Omada
# network ID strings for port-profile or port-override configuration
lookup = client.lan_networks.vlan_id_to_network_id(site_id="your-site-id")
```

`get()`, `update()`, and `delete()` each accept exactly one of `network_id` (Omada
string ID) or `vlan_id` (integer). `update()` fetches the current network before
PATCHing — the Omada API requires the full object on PATCH, so this avoids callers
having to supply every field. `create()` accepts an optional `dhcp_server_enabled`
parameter (default `False`).

### DHCP Snooping

`client.dhcp_snooping` manages DHCP snooping for a site. Omada models it in two
layers: a **site-wide master enable** (`/dhcpSnoops/status`) and **per-device
snoop entries** (`/dhcpSnoops`) listing the client-facing / *untrusted* ports (the
uplink/cascade port is auto-excluded and surfaces in `unSelectedablePorts` on
`get_supported`). Bodies are dict-first — the caller builds the entry shapes.

```python
# Site-wide master enable
enabled = client.dhcp_snooping.get_status(site_id="your-site-id")
client.dhcp_snooping.set_status(site_id="your-site-id", enabled=True)

# List existing snoop entries and switches that support snooping (with selectable ports)
snoops = client.dhcp_snooping.get_snoops(site_id="your-site-id")
supported = client.dhcp_snooping.get_supported(site_id="your-site-id")

# Create per-device entries (the mandatory `devices` envelope is applied for you)
client.dhcp_snooping.create_snoops(
    site_id="your-site-id",
    devices=[{"mac": "AA-BB-CC-DD-EE-FF", "ports": [{"port": 1}, {"port": 2}]}],
)

# Modify or delete one entry, or find an entry by device MAC
client.dhcp_snooping.update_snoop(
    site_id="your-site-id",
    snoop_id="<snoopId>",
    settings={"mac": "AA-BB-CC-DD-EE-FF", "name": "Core-SW", "ports": [{"port": 1}]},
)
client.dhcp_snooping.delete_snoop(site_id="your-site-id", snoop_id="<snoopId>")
entry = client.dhcp_snooping.find_snoop_by_mac(site_id="your-site-id", mac="AA:BB:CC:DD:EE:FF")
```

`create_snoops` wraps the entries in the mandatory top-level `devices` array —
without it the controller returns `errorCode 0` but persists nothing.
`update_snoop` takes a flat `{mac, name, ports}` body (passed through unchanged).
`find_snoop_by_mac` compares MACs format-insensitively (colon vs hyphen) and
returns `None` when there is no match. Note the per-port
`OswPortSettingVO.dhcpSnoopEnable` field is *not* the trust mechanism on tested
hardware; trust is realised through these snoop entries.

### RADIUS Profiles

`client.radius_profiles` manages site RADIUS profiles referenced by 802.1X and
PPSK/DPSK workflows.

```python
auth_servers = [{"ip": "10.0.0.10", "authPort": 1812, "authKey": "shared-secret"}]

# List, or resolve one by id or name (exactly one selector)
profiles = client.radius_profiles.all(site_id="your-site-id")
profile = client.radius_profiles.get(site_id="your-site-id", name="My RADIUS Profile")

# Create
created = client.radius_profiles.create(
    site_id="your-site-id",
    name="My RADIUS Profile",
    auth_servers=auth_servers,
    accounting_enabled=False,
    wireless_vlan_assignment=False,
)

# Update an existing profile by id (same body shape as create)
client.radius_profiles.update(
    site_id="your-site-id",
    profile_id="<radiusProfileId>",
    name="My RADIUS Profile",
    auth_servers=auth_servers,
)

# Create-if-absent by name -> (profile_dict, created: bool)
profile, was_created = client.radius_profiles.upsert(
    site_id="your-site-id",
    name="My RADIUS Profile",
    auth_servers=auth_servers,
)
```

`get` requires exactly one of `id` or `name`, raising `RadiusProfileNotFoundError`
for a miss and `ValueError` for an ambiguous name. `create`/`update`/`upsert`
require a non-empty `name` and a non-empty `auth_servers` list; extra Omada fields
can be passed via `**kwargs`. Omada rejects modifying a profile that is in use by
PPSK/DPSK with error `-34015`, so `upsert` is create-if-absent only (it never
modifies an existing profile).

### OLT / ONU optics (GPON)

`client.olts` queries ONU optical telemetry from an upstream OLT. The Omada API
requires an ONU **`key`** identifier for detail telemetry; this SDK provides a
MAC-based convenience method that resolves the key via the ONU list endpoint.

```python
onu_detail = client.olts.get_onu_detail_by_mac(
    site_id="your-site-id",
    olt_mac="AA-BB-CC-DD-EE-FF",
    pon_port="GPON 1/1/1",
    onu_mac="11-22-33-44-55-66",
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

### Spec source and version pinning

The Omada Open API is effectively unversioned — `info.version` is `v0.1` on both
the TP-Link cloud spec and a controller's own `/v3/api-docs`. The baseline is
therefore anchored to the **controller** version (`controllerVer` + `apiVer` from
`/api/info`) rather than the spec version. `make spec-fetch` writes both the raw
spec (`spec/raw/all.json`) and a version manifest (`spec/raw/manifest.json`)
recording `source`, `controllerVer`, `apiVer`, `spec_info_version`, `spec_sha256`,
and `fetched_at`. `make spec-fix` / `make spec-validate` read `all.json` and are
unaffected by the manifest.

Choose the source:

```bash
# Public TP-Link cloud spec (default; the manifest records null controller versions)
make spec-fetch

# A local controller — set the address in the environment, not in the repo.
# The manifest records only source="controller", never the host/IP.
OMADA_BASE_URL=https://<controller> make spec-fetch-controller

# Equivalent, via passthrough args
make spec-fetch SPEC_FETCH_ARGS='--base-url https://<controller> --insecure'
```

Configuration:

- `OMADA_BASE_URL` (or `--base-url`): controller base URL; the spec is read from
  `{base}/v3/api-docs/00%20All` and the version manifest from `{base}/api/info`.
- `OMADA_OPENAPI_URL` (or `--url`): explicit spec URL override.
- `OMADA_VERIFY=false` (or `--insecure`): disable TLS verification for controllers
  with self-signed certificates.
