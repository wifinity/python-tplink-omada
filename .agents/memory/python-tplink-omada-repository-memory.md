# Python-TPLink-Omada Repository Memory

## Purpose
- Python client library for TP-Link Omada SDN controller workflows used by network automation.

## Architecture conventions
- `OmadaClient` is the single entry point and exposes resource sub-clients.
- Public API is dict-first for ergonomics and backward stability.
- Public resource APIs are keyword-only. Call and define methods on `client.sites`, `client.devices`, `client.aps`, `client.wifi_networks` and `client.ap_groups` with named parameters only.
- Use `mac` as the canonical MAC-address parameter name for device/AP lookup and action methods.
- Validate and normalize MAC inputs with `macaddress` before outbound device/AP MAC path/query usage.
- Canonical outbound MAC format is uppercase hyphen EUI-48: `AA-BB-CC-DD-EE-FF`.
- Generated model artifacts remain internal (`omada_client.generated.models`).
- Site creation API (`SitesResource.create`) uses explicit defaults for Omada-required fields:
  - `region="United Kingdom"`
  - `scenario="Dormitory"`
  - `time_zone="UTC"` mapped to API field `timeZone`
- Site update API (`SitesResource.update`) applies the same defaults when values are omitted:
  - `region="United Kingdom"`
  - `scenario="Dormitory"`
  - `timezone="UTC"` mapped to API field `timeZone`
- Device account credentials are exposed via explicit params:
  - `device_username`
  - `device_password`
  and are required as a pair unless raw `deviceAccountSetting` is passed via `**kwargs`.
- Region input is validated as a full country name using `pycountry`; ISO codes (for example `GB`, `GBR`) are rejected with actionable errors.
- `DevicesResource.start_adopt` accepts optional `username` and `password` parameters and always sends both fields in JSON request body; omitted values default to `admin`.
- AP lookup contract is split explicitly by method:
  - `APsResource.all` returns AP-filtered device collection results via canonical device list semantics.
  - `APsResource.get_by_mac` returns a DeviceInfo-style AP item from AP-filtered device list semantics.
  - `APsResource.get_by_name` returns a DeviceInfo-style AP item resolved by AP name.
  - `APsResource.get_overview_by_mac` returns AP overview endpoint payload (`/aps/{apMac}`), which can differ in shape from DeviceInfo; adds `result.apGroupName` when the AP's group id (reported under `wlanId` on 6.3) resolves via `ap_groups.get`.
  - `APsResource.get_wired_uplink_by_mac` returns AP wired uplink endpoint payload (`/aps/{apMac}/wired-uplink`) and augments `result.wiredUplink` with decoded meaning fields (`portTypeMeaning`, `linkStatusMeaning`, `linkSpeedMeaning`, `duplexMeaning`) while preserving numeric codes.
  - `APsResource.get_by_serial` returns a DeviceInfo-style AP item resolved by serial number (`sn`); filtered client-side (no `searchKey` support for `sn`), raises `DeviceNotFoundError` if not found.
- `SwitchesResource` has the same lookup contract as `APsResource` (mac/name/serial), including `SwitchesResource.get_by_serial` (Decision 38) — DeviceInfo-style, client-side `sn` filter, `DeviceNotFoundError` if not found.
- SDK 2.0 targets controller 6.3+ only (ADR Decision 43). There is no WLAN-group resource; "WLAN group" is the legacy name of AP group, and the ids are identical.
- AP group contract (`APGroupsResource`, `/sites/{siteId}/ap-groups`):
  - `all(*, site_id, search_key=None)` pages via `fetch_all_pages` (pageSize 100; the controller rejects >100 despite the spec's 1000).
  - `get(*, site_id, id|name)`: by id via `/{id}/info`, by name via exact match. `create(*, site_id, name, ap_macs=None)` puts the new id at `result.id`. `update(*, site_id, id|name, new_name=None, add_ap_macs=None, remove_ap_macs=None)` always sends `name`. `delete(*, site_id, id|name)`.
  - `resolve_ids(*, site_id, ap_groups)` maps ids or names to ids with one list call.
  - Missing → `APGroupNotFoundError`; duplicate name → `ValueError`.
  - The controller rejects deleting a group that has APs (-33306) or bound SSIDs (-33305).
  - An AP is in exactly one group; `addApMacs` moves it out of its previous group.
- Wi-Fi networks (`WiFiNetworksResource`) are site-wide SSIDs bound to AP groups via `apGroupIds`. List and create use v2 `/openapi/v2/.../wireless-network/ssids`; get, delete and the per-setting PATCHes use v1 `/wireless-network/ssids/{id}/...`.
  - `create(*, site_id, ap_groups, type, ...)` resolves `ap_groups` to `apGroupIds`; `network_data` must not carry `apGroupIds`.
  - `get_ap_groups` / `set_ap_groups` read and replace the binding.
  - SSID names are unique on a site for create and rename (-33219), but the 6.2→6.3 migration leaves same-name duplicates. So `get(name=)` raises `ValueError` on duplicates; use `filter(name=)`. A missing SSID raises `WiFiNetworkNotFoundError`.
  - `update_rate_control` (and the `rate_control=` step of `create`) PATCHes the deprecated `.../wlans/{firstApGroupId}/ssids/{id}/update-rate-control`, because the site route returns HTTP 500 on 6.3.0.45.
  - Ids are read from `id` before `ssidId`.
  - `create(..., type=..., ssid=None, name=None, ...)` requires at least one of `ssid` or `name` (broadcast name); if both, they must match. JSON field is always `name`.
  - String `type` maps to Omada `security`: `open`/`open-isolated` (0), `aaa` (2), `psk` (3), `ppsk_local` (4), `dpsk` (5). Alias `ppsk-local` → `ppsk_local`. **`psk`** = WPA-Personal (`wpa_basic.json`, `psk=` required); **`ppsk_local`** = corporate PPSK (`wpa.json`, `ppsk_profile_name=`). Cross-type auth kwargs are rejected (`psk=` only on `psk`; `ppsk_profile_name` only on `ppsk_local`). An external `dpsk-local-auth` type is not the same as `ppsk_local`. `open-isolated` sets `guestNetEnable`; `open` may set `guest_network=True/False`. `hotspot20` is rejected with a clear message.
  - `vlan` sets `vlanId` and Anchor-style `vlanSetting` (Omada create requires both when `vlanEnable`); mutually exclusive with `vlan_setting` dict.
  - `ppsk_profile_name` on `ppsk_local` create resolves Omada id via `GET .../ppsk-profiles` (exact `profileName` match); `radius_profile_name`+`nas_id` for `dpsk` resolves id via `GET .../profiles/radius` (exact `name` match; not with `ppsk_setting`).
  - `pmf_mode` overrides defaults (`2` open/open-isolated, `3` psk/ppsk_local/dpsk); `mac_format` defaults to `2`.
  - `multicast_config={...}` on create POSTs then PATCHes flat `UpdateSsidMultiCastOpenApiVO` fields when set (before optional `rate_control`, then rate limit); reject nested `multiCast` wrapper. `update_multicast_config(..., multicast_data=...)` requires explicit dict (no SDK preset builders; callers own their own GUEST/SECURED dicts).
  - Every `create()` POSTs then PATCHes `rate-limit` with site profile `name=="Default"` unless `rate_limit_profile_id` is set; `update_rate_limit(...)` for standalone PATCH. `build_rate_limit_profile_body(profile_id)` builds nested PATCH body (limits off in customSetting).
  - `rate_control={...}` on create POSTs then PATCHes rate control (legacy nested route, see above) with caller-supplied flat dict (`UpdateSsidRateControlOpenApiVO` fields); after multicast PATCH when both are set. No SDK template builder — define the dict in the caller; GET nests under `detail["rateControl"]`, PATCH body is flat. `update_rate_control(...)` for standalone PATCH.
  - Use package helper `strip_ssid_detail_for_create` when cloning from GET detail into a create body.
  - `filter(*, site_id, **criteria)` lists every page via `all`, then matches by equality client-side. Criterion keys are strict (site SSID list item fields, plus `ssidEnable`), and the `ssid` criterion matches JSON `name`.
  - `update_basic_config(*, site_id, id|name, network_data=None, vlan=None, **kwargs)` GETs the detail, merges it into `UpdateSsidBasicConfigOpenApiVO` and PATCHes `.../ssids/{id}/basic-config`. `ssid` in overrides maps to `name`. A `vlanSetting` with mode 0 is sent as `{"mode": 0}`, because the controller rejects an echoed empty `customConfig` with -1001.
  - Package helper `ssid_detail_to_basic_config_patch` projects GET detail + overrides for that PATCH body.
- DeviceInfo lookup responses are enriched with decoded status labels when numeric fields exist:
  - `statusMeaning` derived from `status`
  - `detailStatusMeaning` derived from `detailStatus`
  - unknown values use deterministic fallbacks (`Unknown status: <code>`, `Unknown detailStatus: <code>`).

## Auth conventions
- OAuth2 client credentials via `/openapi/authorize/token`.
- Token cache is in-memory with refresh buffer.
- 401 responses clear token cache and raise auth-specific exception.

## Spec patching workflow
- Fetch upstream spec into `spec/raw/all.json`.
- Normalize/patch into `spec/fixed/all-fixed.json` with `tools/fix_spec.py`.
- Keep patch files under `spec/patches/` aligned to upstream `omada-go-sdk` patch filenames/content where possible.
- Current upstream-aligned local patch set is:
  - `authentication.json`
  - `createNewSite.json`
  - `DstTimeDTO.json`
- Validate fixed spec before model generation.
- Local dedicated `operation-id-fixes.json` safety path was removed after upstream patch alignment; current validation passes without it.

## Testing and CI
- Run `make spec-fix`, `make spec-validate`, `make generate-models`, `make tests`.
- Keep spec output deterministic and committed when patch behavior changes.

## Updating this memory
- Append major architecture or workflow decisions rather than rewriting history.
- Link new ADRs and notable constraints for future sessions.

## ADR conventions
- Public-repo sanitization (Decision 35) applies to every file, including new ADR entries, README examples, and test fixtures: no internal repo/service/system names, private test names, real site/network IDs, real device MACs or serials, controller hosts, or credentials. Use placeholders (`your-site-id`) and documentation MACs (`AA-BB-CC-DD-EE-FF`, `11-22-33-44-55-66`). Controller version / device model / firmware are publishable (that is the COMPATIBILITY.md matrix).
- ADR history is intentionally maintained as a single evolving file:
  - `docs/adr.md`
- Multiple accepted decisions are recorded as distinct decision sections within that file (not separate ADR files).
- Decision headings in `docs/adr.md` are numeric and ordered (`Decision 1`, `Decision 2`, ...).
- Named-parameter policy is recorded in `docs/adr.md` Decision 7 and should be applied to all future public resource API changes.
- MAC validation/normalization policy is recorded in `docs/adr.md` Decision 8 and should be applied to all future public resource APIs that accept MAC input.
- Start-adopt request-body contract is recorded in `docs/adr.md` Decision 9 and should be preserved for future device adoption API changes.
- AP DeviceInfo-vs-overview method split is recorded in `docs/adr.md` Decision 10 and should be preserved in future AP API additions.
- DeviceInfo status/detail-status enrichment policy is recorded in `docs/adr.md` Decision 11 and should be applied to future DeviceInfo-returning lookup helpers.
- AP adopt/check facade delegation policy is recorded in `docs/adr.md` Decision 12 and should be preserved for future typed-resource convenience shortcuts.
- AP group and site SSID contract is recorded in `docs/adr.md` Decision 43 (supersedes 13/14) and should be followed for future additions.
- AP wired uplink enum-decoding policy is recorded in `docs/adr.md` Decision 15 and should be preserved for future AP wired uplink payload changes.
- Site update defaulting policy is recorded in `docs/adr.md` Decision 16 and should be preserved for future site update API changes.
- Wi-Fi SSID create expanded types and `strip_ssid_detail_for_create` are recorded in `docs/adr.md` Decision 18 and should be applied to future Wi-Fi create API changes.
- Wi-Fi SSID `filter` / `update_basic_config` and `ssid_detail_to_basic_config_patch` are recorded in `docs/adr.md` Decision 19.
- Wi-Fi SSID rate control (`rate_control` on create, `update_rate_control`) is recorded in `docs/adr.md` Decision 20; rate-control templates live outside the SDK.
- Wi-Fi SSID generic multicast (`multicast_config` on create) is recorded in `docs/adr.md` Decision 22; multicast preset dicts live outside the SDK, in the caller.
- Wi-Fi create type `open-isolated` (replaces `guest`) is recorded in `docs/adr.md` Decision 23.
- PPSK profile name lookup on `ppsk_local` create is recorded in `docs/adr.md` Decision 24 (`ppsk_profile_name`, not `ppsk_profile_id`).
- Switch LAN port-profile CRUD (`create_port_profile`, `update_port_profile`, `delete_port_profile`, `upsert_port_profile` on `SwitchesResource`, v2 `/lan-profiles`) is recorded in `docs/adr.md` Decision 31; upsert returns `(dict, created)` and updates on conflict (unlike Decision 28's create-if-absent RADIUS upsert).
- Device-tier STP setter `SwitchesResource.update_loopback_control(*, site_id, switch_mac, settings)` is recorded in `docs/adr.md` Decision 33: **PUT** (not PATCH) `.../switches/{switchMac}/config/loopback` with a `SwitchLoopbackControl` dict passed through verbatim. Sets device-global STP mode (`stp`: 0 OFF/1 STP/2 RSTP/3 MSTP) and bridge priority (`priority`: 0..61440, divisible by 4096) — the only genuinely device-global bridge priority (per-port `spanningTreeSetting.priority` is unrelated). PUT-only (no GET twin) so it is idempotent; no read-before-write. STP/DHCP settings are NOT on `SwitchGeneralConfig`. There is no device/site-global DHCP-snooping enable in the Omada API (only per-port `dhcpSnoopEnable` or per-site `/dhcpSnoops` rules). Any translation into Omada enums/values lives in the caller, not the SDK.
- Per-port switch config setter `SwitchesResource.update_switch_port(*, site_id, switch_mac, port, settings)` is recorded in `docs/adr.md` Decision 32: PATCH `.../switches/{switchMac}/ports/{port}` with an `OswPortSettingVO` dict passed through verbatim (no validation/translation/defaulting/VLAN resolution). Single-port only. Admin enable/disable stays profile-based via `set_port_profiles` (Decision 30) — `disable` is only an override field (`profileOverrideEnable=true`), not the admin toggle. **Verified against a live controller:** the endpoint is NOT a sparse patch despite being HTTP PATCH — partial bodies return Omada "General error"; the caller must send a full `OswPortSettingVO` built from `get_ports` filtered to writable keys (drop read-only `id`/`portStatus`/`portCap`/`portSpeedCap`/`profileName`/`standardPort`). That read-before-write merge lives in the calling workflow layer, not the SDK. `poe` config is not surfaced in the `OswPortVO` read (only operational `portStatus.poe`).
