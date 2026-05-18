# ADR: Architecture decisions (single-file ADR log)

## Status
Accepted

## ADR file convention
This repository maintains ADR decisions in a single evolving file (`docs/adr.md`) rather than creating a new ADR file per decision.

---

## Decision 1 (2026-04): Hand-written client with patched OpenAPI and internal generated models

### Context
The Omada published OpenAPI spec has known quality gaps (missing path parameters, inconsistent content types, and unstable operation IDs), which makes full end-to-end client generation brittle for a stable public SDK.

### Decision
Use a hand-written resource-oriented client API with:
- deterministic spec patching workflow (`spec/raw` -> `spec/fixed`)
- issue-focused patch overlays in `spec/patches`
- internal generated model artifacts used for validation/indexing only
- dict-first public methods for long-term ergonomics and compatibility

### Alternatives considered
1. Full generated client from raw spec
   - rejected due to unstable output and poor ergonomics under current spec defects
2. Fully manual client and manual models only
   - rejected due to higher schema drift risk and maintenance burden

### Consequences
- Better public API ergonomics and consistency with sibling internal Python SDKs.
- Ongoing maintenance is required for patch overlays as upstream spec changes.
- CI must validate fixed spec and generated internal artifacts to keep outputs deterministic.

---

## Decision 2 (2026-04): Align local spec patches with upstream `omada-go-sdk` conventions

### Context
Local patch overlays had drifted from upstream patch naming/content patterns, increasing maintenance surface and reducing cross-project consistency.

### Decision
- Align local patch overlays to `omada-go-sdk` patch naming and content conventions where compatible.
- Use upstream-equivalent files in `spec/patches`:
  - `authentication.json`
  - `createNewSite.json`
  - `DstTimeDTO.json`
- Remove local-only patch files that are not present upstream when they are no longer required.
- Remove dedicated local `operation-id-fixes` safety handling because `make spec-fix` and `make spec-validate` pass without it after alignment.

### Consequences
- Lower local maintenance burden for patch overlays.
- Better compatibility with upstream patch evolution.
- Any future divergence from upstream patch set must be documented in this ADR file with rationale and validation impact.

---

## Decision 3 (2026-04): Local-controller-only API contract

### Context
The validated and supported contract for this SDK is local Omada controller operation. Carrying `deployment` and `region` concepts in the public API added complexity without matching the intended usage model.

### Decision
- Simplify the public SDK surface to local-controller-only operation.
- Remove `deployment` and `region` concepts from `OmadaClient` and endpoint resolution.
- Require `OmadaClient` inputs: `base_url` and `omadac_id`.
- Unify auth to the local contract:
  - token request: `POST /openapi/authorize/token`
  - query: `grant_type=client_credentials`
  - JSON body: `omadacId`, `client_id`, `client_secret`
  - API header: `Authorization: AccessToken=<token>`
- Centralize path handling in client `api_path()` so `/openapi/v1/...` calls are deterministically rewritten to `/openapi/v1/{omadacId}/...`.
- Track `{omadacId}` path inventory/mapping in `docs/omadacid-path-inventory.md`.

### Consequences
- Clearer and smaller public API contract.
- Breaking change for callers relying on deployment/region abstractions.
- More deterministic URL construction and authentication behavior.

---

## Decision 4 (2026-04): Site creation defaults and explicit device credentials

### Context
Omada site creation requires `region`, `scenario`, `timeZone`, and `deviceAccountSetting`.
The previous `SitesResource.create()` surface did not align with this requirement and used `tz` instead of `timeZone`, leading to avoidable runtime validation failures.

### Decision
- Update `SitesResource.create()` to expose explicit, ergonomic parameters:
  - `region` (default: `United Kingdom`)
  - `scenario` (default: `Dormitory`)
  - `time_zone` (default: `UTC`, mapped to request field `timeZone`)
  - `device_username` and `device_password`
- Require `device_username` and `device_password` to be provided together unless callers pass raw `deviceAccountSetting` via `**kwargs`.
- Validate `region` as a full country name using `pycountry`:
  - accept full names case-insensitively
  - reject ISO code inputs like `GB`/`GBR` with actionable error messages
- Preserve advanced overrides through `**kwargs`, with explicit parameters taking precedence.

### Consequences
- Site creation works with a smaller and safer call surface for the primary use case.
- Payloads now conform to Omada field names and required attributes by default.
- Consumers get earlier, clearer validation errors for region and credentials.
- New dependency on `pycountry` is required for client-side region validation.

---

## Decision 5 (2026-04): Canonical site read contract for `all()` and `get(...)`

### Context
Site lookup support was added with `client.sites.all()` and `client.sites.get(...)` (`id` or `name`).
Omada's site list endpoint requires paging parameters and returns summary objects, while the site detail endpoint returns the canonical full entity.
Returning list summaries from `get(name=...)` created shape differences versus `get(id=...)`.

### Decision
- Implement `client.sites.all(params=...)` as a single-page list call to `GET /openapi/v1/{omadacId}/sites`.
- Apply default paging params in `all()`:
  - `page=1`
  - `pageSize=1000`
  while allowing caller overrides via `params`.
- Implement `client.sites.get(id=...)` as `GET /openapi/v1/{omadacId}/sites/{siteId}` and return the detail entity payload.
- Implement `client.sites.get(name=...)` as:
  1. list query (`searchKey=name`) to resolve `siteId`
  2. canonical detail fetch by `siteId`
- Require exactly one selector for `get(...)` (`id` xor `name`) and raise `ValueError` for invalid or ambiguous matches.

### Consequences
- `get(id=...)` and `get(name=...)` now return the same canonical payload shape.
- `all()` supports paging controls but intentionally remains a one-page call (no auto-pagination loop).
- Name-based lookup incurs one additional API request in exchange for consistent detail output.

---

## Decision 6 (2026-04): Canonical device action layer with typed resource facades

### Context
Device workflows need consistent operations (list/get/create/delete) across multiple device types.
AP support is needed now, and similar support for switches is expected later.
Duplicating low-level endpoint logic in each resource increases maintenance cost and behavior drift risk.

### Decision
- Make `DevicesResource` the canonical endpoint/action layer for shared device CRUD-like operations.
- Add canonical methods in `DevicesResource` for:
  - list devices in a site
  - get device info by MAC
  - create/register device in a site
  - delete/forget device by MAC
- Implement type-specific resources (for example `APsResource` now, `SwitchesResource` in future) as thin facades over `DevicesResource`.
- Use AP-specific options and AP-specific endpoint paths only where required, while keeping core request construction and semantics in `DevicesResource`.
- Keep path construction compatible with `OmadaClient.api_path()` rewriting.

### Consequences
- New device-type resources can be added faster with lower duplicate code.
- Behavior for shared device actions stays consistent across resource namespaces.
- Backward compatibility is preserved by retaining existing `DevicesResource` methods alongside canonical aliases.
- Some type-specific lookups may still need specialized endpoint paths, but those should be composed through the shared layer first.

---

## Decision 7 (2026-04): Named-parameter-only public resource APIs

### Context
Resource methods had mixed positional and keyword calling patterns, which made call sites less explicit and increased the chance of argument-order mistakes during API evolution.

### Decision
- Enforce keyword-only signatures for public resource methods exposed through:
  - `client.sites`
  - `client.devices`
  - `client.aps`
  - `client.wifi_networks`
  - `client.wlan_groups`
  - `client.ap_groups`
- Standardize MAC argument naming to `mac` for device/AP lookup and action methods.
- Treat positional usage for these public resource methods as unsupported.

### Consequences
- Call sites become self-describing and safer to refactor.
- This is a breaking change for consumers currently passing positional arguments to public resource methods.
- Future public resource API additions should follow keyword-only signatures by default.

---

## Decision 8 (2026-04): MAC validation and canonical formatting with `macaddress`

### Context
Public device/AP methods accept MAC addresses and pass them into Omada request paths and query filters.
Omada expects MAC values in uppercase hyphen form (`AA-BB-CC-DD-EE-FF`), but callers commonly provide other valid EUI-48 forms (`:`, bare hex, dot notation).
Without centralized normalization, behavior can drift across methods and matching logic can fail when response MAC formatting differs from caller input formatting.

### Decision
- Add client-side MAC validation and normalization via the `macaddress` dependency.
- Introduce a shared helper (`normalize_mac`) that:
  - validates input using `macaddress.MAC`
  - accepts supported EUI-48 input forms
  - returns canonical Omada format `AA-BB-CC-DD-EE-FF`
  - raises a clear `ValueError` for invalid MAC input
- Apply normalization to public methods that accept `mac` in `DevicesResource` and `APsResource` before outbound path/query construction.
- Normalize MAC comparison values in `DevicesResource.get_by_mac(...)` so matching is format-insensitive across response fields (`mac`, `deviceMac`, `macAddress`).

### Consequences
- Outbound Omada requests use a consistent MAC format for all public device/AP MAC entry points.
- Consumers can pass common valid EUI-48 forms while still getting strict validation errors for invalid values.
- Adds and standardizes dependency usage on `macaddress` for MAC parsing/normalization behavior.

---

## Decision 9 (2026-04): `start_adopt` request body includes optional credentials with `admin` defaults

### Context
The Omada `start-adopt` endpoint requires a JSON request body for adopt operations.
The previous `DevicesResource.start_adopt(...)` implementation sent no body, which can return HTTP 400 from controllers that enforce the endpoint contract.
Callers also need an ergonomic way to provide device login credentials when adoption requires them.

### Decision
- Extend `DevicesResource.start_adopt(...)` to accept optional keyword-only parameters:
  - `username`
  - `password`
- Always send a JSON body to `/devices/{deviceMac}/start-adopt` with both fields:
  - defaults: `{"username": "admin", "password": "admin"}`
  - explicit values when provided by the caller
- Keep `mac` normalization behavior unchanged so outbound MAC formatting remains canonical.

### Consequences
- Start-adopt calls now conform to the Omada request-body contract even when credentials are not supplied.
- Existing call sites that pass only `site_id` and `mac` remain compatible.
- Credentialed adoption flows can be expressed directly through a single public resource method.

---

## Decision 10 (2026-04): Split AP DeviceInfo lookup from AP overview payload

### Context
`client.aps.get_by_mac(...)` previously returned data from the AP overview endpoint (`/aps/{apMac}`),
while AP collection workflows (`client.aps.all(...)`) returned DeviceInfo entries from `/devices` with `deviceType=ap`.
This created an avoidable payload-shape mismatch for callers expecting `status`/`detailStatus` and
other DeviceInfo fields when resolving APs by MAC.

### Decision
- Make `client.aps.get_by_mac(...)` return a DeviceInfo-style AP item by resolving through the AP-filtered
  device list workflow.
- Add `client.aps.get_by_name(...)` as a DeviceInfo-style AP lookup by name.
- Expose AP overview payloads explicitly via `client.aps.get_overview_by_mac(...)` for callers that need the
  `/aps/{apMac}` shape.

### Alternatives considered
1. Keep `get_by_mac` on AP overview shape and add `get_device_info_by_mac`
   - rejected because the primary lookup name should return the canonical list-aligned AP device record.
2. Keep only overview behavior and document shape differences
   - rejected because this preserved ambiguity and repeated user confusion.

### Consequences
- `client.aps.get_by_mac(...)` is a behavior change and now aligns with DeviceInfo-style AP list entries.
- Existing consumers depending on AP overview fields from `get_by_mac(...)` must migrate to
  `client.aps.get_overview_by_mac(...)`.
- AP lookup contracts are now explicit by method name, reducing shape ambiguity in downstream automation.

---

## Decision 11 (2026-04): Decode DeviceInfo `status` and `detailStatus` into meaning fields

### Context
DeviceInfo payloads include numeric `status` and `detailStatus` values. While codes are defined in the
spec, consumers otherwise need to duplicate mapping logic locally to render understandable state.

### Decision
- Enrich DeviceInfo-shaped lookup responses with:
  - `statusMeaning`
  - `detailStatusMeaning`
- Apply this enrichment for DeviceInfo-returning lookup helpers (for example:
  - `client.devices.get_by_mac(...)`
  - `client.aps.get_by_mac(...)`
  - `client.aps.get_by_name(...)`)
- Keep AP overview payload methods (for example `client.aps.get_overview_by_mac(...)`) as their
  native endpoint shape and do not force DeviceInfo-specific enrichment there.
- For unknown numeric codes, keep original values and add deterministic fallback strings:
  - `Unknown status: <code>`
  - `Unknown detailStatus: <code>`

### Consequences
- Downstream callers can rely on stable, human-readable state fields without managing enum tables.
- Existing numeric fields are preserved for programmatic filtering and compatibility.
- New status/detail-status code additions in controller versions remain forward-compatible through
  fallback strings until mapping tables are updated.

---

## Decision 12 (2026-04): AP adopt/check shortcuts delegate to canonical devices layer

### Context
Adoption flows are canonical on `client.devices` (`start_adopt` and `check_adopt`), while
`client.aps` is a typed facade intended to provide AP-focused entry points for common workflows.
AP users otherwise need to switch resource namespaces for adoption operations.

### Decision
- Add AP facade shortcuts:
  - `client.aps.start_adopt(...)`
  - `client.aps.check_adopt(...)`
- Implement both as thin delegations to:
  - `client.devices.start_adopt(...)`
  - `client.devices.check_adopt(...)`
- Keep the public method signatures keyword-only and retain `mac` as the parameter name.
- Keep normalization and adopt-result augmentation in `DevicesResource` as the canonical behavior.

### Consequences
- AP-centric call sites can perform adopt workflows without leaving `client.aps`.
- Shared adopt behavior remains centralized, reducing drift and duplication.
- Future AP-specific resources should continue to add convenience methods via delegation first.

---

## Decision 13 (2026-04): Site-scoped WLAN groups resource with name-based resolution

### Context
WLAN group operations are exposed by Omada under site-scoped wireless-network endpoints.
The SDK needed first-class WLAN group workflows while preserving the repository's
named-parameter policy and selector ergonomics already used in `SitesResource`.

### Decision
- Add `client.wlan_groups` as a public resource with keyword-only methods:
  - `all(*, site_id, params=None)`
  - `create(*, site_id, name=None, group_data=None)`
  - `get(*, site_id, id=None, name=None)`
  - `delete(*, site_id, id=None, name=None)`
- Keep methods site-scoped via `site_id` to match Omada endpoint contracts.
- Default create payload field `clone=False` when callers do not provide `clone`.
- For `get(...)` and `delete(...)`, require exactly one selector (`id` xor `name`).
- Implement name-based resolution with exact-name matching over list results and raise
  `WLANGroupNotFoundError` for missing groups, plus explicit `ValueError` cases for duplicates
  and missing `wlanId`.
- Keep request paths compatible with `OmadaClient.api_path()` rewriting.

### Consequences
- WLAN group workflows are available through a consistent resource namespace in the SDK.
- Callers get deterministic selector behavior aligned with existing site lookup patterns.
- Name-based delete/get flows may require an additional list call before the terminal action.

---

## Decision 14 (2026-04): Wi-Fi networks are SSIDs nested under WLAN groups

### Context
Omada exposes Wi-Fi network (SSID) operations under site + WLAN-group scoped endpoints:
`/sites/{siteId}/wireless-network/wlans/{wlanId}/ssids`.
The SDK previously had only a minimal Wi-Fi resource contract and needed first-class
`all/get/delete/create` workflows aligned to the repository's keyword-only public API policy.

### Decision
- Implement `client.wifi_networks` as a site + WLAN-group scoped resource with keyword-only methods:
  - `all(*, site_id, wlan_group, params=None)`
  - `get(*, site_id, wlan_group, id=None, name=None)`
  - `delete(*, site_id, wlan_group, id=None, name=None)`
  - `create(...)` (see Decision 18 for `type` mapping, broadcast-name rules, and VLAN shortcuts).
  - `filter(*, site_id, wlan_group, **criteria)` and `update_basic_config(...)` (Decision 19).
- Resolve `wlan_group` as id-or-name via `client.wlan_groups.get(...)`.
- Require exactly one selector (`id` xor `name`) for `get(...)`, `delete(...)`, and `update_basic_config(...)`, with exact-name matching for name selectors.
- Keep Wi-Fi create ergonomic with string `type` while mapping to Omada numeric `security` values (Decision 18).

### Consequences
- Wi-Fi network operations are now consistent with existing resource patterns (`sites`, `wlan_groups`).
- SDK behavior matches Omada nesting semantics and avoids ambiguity about WLAN group scope.
- Create flows remain ergonomic for callers while preserving explicit Omada payload control via overrides.
- Extended create ergonomics and Omada `security` mode coverage are governed by Decision 18.
- Client-side `filter(...)` and merge-from-GET `update_basic_config(...)` are governed by Decision 19.

---

## Decision 15 (2026-04): Decode AP wired uplink enums into human-readable meaning fields

### Context
`client.aps.get_wired_uplink_by_mac(...)` returns numeric enum-like fields under
`result.wiredUplink` (for example `portType`, `linkStatus`, `linkSpeed`, `duplex`).
Consumers otherwise need to duplicate mapping tables to render understandable uplink state.

### Decision
- Enrich AP wired uplink payloads with decoded meaning fields while preserving numeric values:
  - `portTypeMeaning` derived from `portType`
  - `linkStatusMeaning` derived from `linkStatus`
  - `linkSpeedMeaning` derived from `linkSpeed`
  - `duplexMeaning` derived from `duplex`
- Apply this enrichment in `client.aps.get_wired_uplink_by_mac(...)` on the native endpoint
  response shape (`result.wiredUplink`).
- Keep fallback handling deterministic for unknown numeric codes:
  - `Unknown portType: <code>`
  - `Unknown linkStatus: <code>`
  - `Unknown linkSpeed: <code>`
  - `Unknown duplex: <code>`

### Consequences
- Downstream callers get stable human-readable uplink state without maintaining local enum maps.
- Raw numeric fields remain available for filtering and compatibility.
- New controller enum values remain forward-compatible via unknown-code fallback strings until
  mappings are explicitly updated.

---

## Decision 16 (2026-04): Apply site update defaults by default

### Context
Site creation already applies required Omada fields by default (`region`, `scenario`, `timeZone`),
but update callers that omitted those inputs relied on ad-hoc wrapper behavior and could leak null-like
values into update requests.
This caused avoidable runtime API failures in automation wrappers where update payloads were built from
partially populated input context.

### Decision
- Make `SitesResource.update(...)` apply the same default values used by create when update values are omitted:
  - `region="United Kingdom"`
  - `scenario="Dormitory"`
  - `timezone="UTC"` mapped to `timeZone`
- Preserve explicit caller overrides when values are provided.
- Keep region validation for the effective region value in update requests.

### Consequences
- Update calls are safer by default for primary automation workflows.
- Omitted update fields now produce deterministic Omada-compatible payloads instead of omission semantics.
- Wrappers can still set explicit non-default values when required by workflow policy.

---

## Decision 17 (2026-05): Add OLT/ONU optics resource with MAC-to-key resolution

### Context
Omada exposes GPON ONU telemetry (optical power, voltage, bias current, temperature, etc.) via OLT-scoped endpoints.
The ONU detail endpoint requires an internal ONU identifier (`key`, for example `1-1-1_0`) rather than the ONU's MAC
address, which makes direct “MAC → optics” workflows awkward for automation.

### Decision
- Add a new public resource `client.olts` to encapsulate OLT/ONU operations with keyword-only methods:
  - `list_onus(*, site_id, olt_mac, pon_port, params=None)`
  - `get_onu_detail(*, site_id, olt_mac, onu_key, params=None)` (detail endpoint requires `key`)
  - `resolve_onu_key(*, site_id, olt_mac, pon_port, onu_mac)` (list + MAC match → `key`)
  - `get_onu_detail_by_mac(*, site_id, olt_mac, pon_port, onu_mac, params=None)` (convenience: resolve key then fetch detail)
- Normalize MAC inputs for path construction and matching, using the existing `macaddress`-based helper.
- Return API payloads as-is (no field renaming or unit normalization) to preserve Omada compatibility and avoid
  creating a second “normalized schema” surface.
- Keep request paths compatible with `OmadaClient.api_path()` rewriting.

### Consequences
- Downstream automation can query ONU optics by MAC with a single call (`get_onu_detail_by_mac`), while retaining
  access to the underlying key-based primitive (`get_onu_detail`).
- The `key` identifier caveat is captured in a single place and insulated behind the resource API surface.
- Payload shapes remain controller-defined; callers that need stable field names should implement their own
  normalization layer outside the SDK.

---

## Decision 18 (2026-05): Wi-Fi SSID create — Ruckus-like types, broadcast name, VLAN, clone helper

### Context
Omada `CreateSsidOpenApiVO` uses numeric `security` (0 none, 2 WPA-Enterprise, 3 WPA-Personal, 4 PPSK without RADIUS,
5 PPSK with RADIUS). Callers migrating from sibling clients (for example Ruckus One) expect string `type` discriminators,
optional `name` alongside `ssid`, guest-style open SSIDs, PPSK-without-RADIUS (`security=4`), and VLAN shapes that match
the controller (`vlanSetting` vs plain `vlanId`). GET SSID detail payloads are a superset of create fields.

### Decision
- Expand `WiFiNetworksResource.create(...)` keyword-only parameters:
  - `ssid` and `name` are both optional but **at least one required**; if both are set they must be identical (broadcast SSID string maps to JSON `name`).
  - `vlan_setting` accepts Omada `vlanSetting` object; mutually exclusive with the integer `vlan` parameter.
  - `guest_network` applies to `type="open"` only: when `True`/`False`, sets `guestNetEnable`; when omitted, leaves default from payload builder.
  - `type="open-isolated"` is sugar for open SSID with `guestNetEnable=True` (`security=0`), not Hotspot 2.0 / captive portal parity with Ruckus `hotspot20`.
  - `type="ppsk_local"` maps to `security=4` and requires both `psk_setting` or `psk` **and** `ppsk_setting`.
  - `type="dpsk"` remains `security=5` (PPSK with RADIUS) and requires `ppsk_setting`.
  - `type="hotspot20"` remains unsupported with an explicit error directing callers to future HotspotV2 work or raw HTTP.
- Export `strip_ssid_detail_for_create` from `omada_client` to trim GET detail dicts to `CreateSsidOpenApiVO` keys before merge/create.

### Consequences
- Automation can mirror Ruckus-style `create(name=..., type=..., ...)` call sites where `name` is the SSID string.
- PPSK-without-RADIUS and guest-style open networks are first-class without dumping full payloads for every field.
- Callers cloning from GET responses should use `strip_ssid_detail_for_create` then override secrets/ids before POST.

---

## Decision 19 (2026-05): Wi-Fi SSID `filter` and `update_basic_config`

### Context
Sibling clients (for example Ruckus One) document `wifi_networks.filter(...)`, `wifi_networks.update(id, {...})`,
and a linear list/get/create/delete story. Omada SSIDs remain nested under a site and WLAN group, and updates use
PATCH `.../ssids/{ssidId}/update-basic-config` with `UpdateSsidBasicConfigOpenApiVO` rather than a single PUT replace.

### Decision
- Add `WiFiNetworksResource.filter(*, site_id, wlan_group, **criteria)` (keyword-only):
  - Load SSIDs via existing `all(...)`; apply **client-side** equality filtering on list item top-level keys.
  - Accept only a **strict allowlist** of criterion names; unknown keys raise `ValueError`.
  - Treat criterion `ssid=` as an alias for the broadcast string stored in JSON **`name`**.
  - When criteria are only broadcast-name selectors (`name` and/or matching `ssid`), pass `searchKey` on the list GET
    for a smaller controller response, then still enforce exact equality client-side.
- Add `WiFiNetworksResource.update_basic_config(*, site_id, wlan_group, id|name, network_data=None, **kwargs)`:
  - `get(...)` current detail, project to `UpdateSsidBasicConfigOpenApiVO` keys, merge `network_data` then `kwargs`,
    validate required basic-config fields, PATCH `update-basic-config`.
  - Map override key `ssid` to `name` when callers mirror Ruckus `{"ssid": "..."}` payloads.
- Export pure helper `ssid_detail_to_basic_config_patch` from `omada_client` for the projection + merge + validation
  step without repeating allowlists at call sites.
- Do **not** fold other SSID PATCH endpoints (rate limit, schedule, HotspotV2, …) into this method; callers use raw
  `client.patch` if they need those surfaces.

### Consequences
- README examples can follow the same narrative order as Ruckus (`all` / `get` / `filter` / `create` / `update` / `delete`)
  while staying honest about Omada path and merge semantics.
- Callers must not assume `update_basic_config` is a partial no-merge PATCH; missing required fields after merge raise
  a clear error pointing to incomplete GET detail or overrides.

---

## Decision 20 (2026-05): Wi-Fi SSID rate control (`update_rate_control`, `rate_control` on create)

### Context
Omada SSID **create** does not include `rateControl`. Rate settings use PATCH
`.../ssids/{ssidId}/update-rate-control` with a flat `UpdateSsidRateControlOpenApiVO` body. GET detail nests
settings under `detail["rateControl"]`. Reference field values are documented in
`docs/wlan_samples/*.json` (the `rateControl` key there is GET/reference shape, not the PATCH body).

### Decision
- Add `WiFiNetworksResource.update_rate_control(*, site_id, wlan_group, id|name, rate_control)`:
  - `rate_control` is **required**; must be a non-empty dict of flat PATCH fields.
  - Reject nested wrapper key `rateControl` with an actionable error (PATCH body is flat, not GET-shaped).
- Add optional `rate_control: dict | None = None` on `create(...)`:
  - When a dict is provided, after POST (and after optional `multicast_config` multicast PATCH when set), resolve
    `ssidId` and PATCH `update-rate-control` with the same dict.
  - Valid for all supported `type` values.
- **Do not** add `build_rate_control_setting()` or export a default rate-control template from `omada_client`;
  StackStorm packs and other callers own the constant (aligned with `docs/wlan_samples`).
- Out of scope (Decision 20): rate **limit** profiles (`update-rate-limit`), bool shortcut (`rate_control=True`), merging
  partial dicts from GET detail.

### Consequences
- Post-create rate control matches the optional `multicast_config` POST-then-PATCH pattern (Decision 22).
- README points to `docs/wlan_samples` for field reference; callers must not pass GET-nested `rateControl` wrappers.
- Pack shims pass `rate_control=RATE_CONTROL` into `create` or call `update_rate_control` on existing SSIDs.

---

## Decision 21 (2026-05): Wi-Fi SSID rate limit profile by name (`update_rate_limit`, `rate_limit_profile_name` on create)

### Context
GET SSID detail includes `clientRateLimit` and `ssidRateLimit` with a site `profileId` and `customSetting` limits disabled
(see `docs/wlan_samples`). Create does not set rate limits; Omada uses PATCH `update-rate-limit` with
`UpdateSsidRateLimitOpenApiVO` (nested `clientRateLimit` / `ssidRateLimit`, unlike flat rate **control** PATCH).
New SSIDs otherwise only expose `customSetting` without a profile until configured. Callers (StackStorm,
NetBox-driven automation) know the Omada **profile name** (e.g. `Default`) but not the opaque `profileId`.

### Decision
- Add `WiFiNetworksResource.update_rate_limit(*, site_id, wlan_group, id|name, rate_limit_profile_name)`:
  - `rate_limit_profile_name` is **required**; resolved before PATCH via `GET /sites/{siteId}/rate-limit-profiles`,
    exact match on list item `name`, use `profileId`. **0 matches:** `ValueError`; **>1 matches:** `ValueError`
    listing conflicting `profileId`s. Mirrors the PPSK/RADIUS name lookup (Decisions 24/25).
  - PATCH body from `_build_rate_limit_profile_body(profile_id)` (same profile on client and SSID; custom limits off).
- Add optional `rate_limit_profile_name: str | None = None` on `create(...)`:
  - When provided, after POST resolve `ssidId` and PATCH `update-rate-limit` (after optional multicast and
    rate-control PATCHes). When omitted, **no** rate-limit GET or PATCH is performed.
- No SDK-exported default rate-limit template dict (callers/stackstorm own constants); helper `_build_rate_limit_profile_body` is structural only.

### Consequences
- Rate-limit is opt-in, consistent with `multicast_config` and `rate_control` (Decisions 20/22): a plain
  `create()` does only the POST, with no dependency on a site profile named `Default` existing.
- Callers attach a profile by passing `rate_limit_profile_name="Default"` (or another profile name).
- Rate **control** (802.11 rates) remains separate from rate **limit** (throughput profiles); Decision 20 unchanged.

---

## Decision 22 (2026-05): Wi-Fi SSID generic multicast (`multicast_config` on create)

### Context
Omada SSID **create** does not set multicast/broadcast management. Settings use PATCH
`.../ssids/{ssidId}/update-multicast-config` with flat `UpdateSsidMultiCastOpenApiVO` fields. GET detail nests under
`detail["multiCast"]`. Guest and secured presets are documented in `docs/wlan_samples` (flat keys for PATCH).
The SDK previously exposed `guest_multicast_filter=True` and `build_guest_multicast_setting()` for guest-only parity;
secured SSIDs (for example `ppsk_local`) left `arpCastEnable` false unless callers PATCHed manually.

### Decision
- Add optional `multicast_config: dict | None = None` on `create(...)`:
  - When a dict is provided, after POST resolve `ssidId` and PATCH `update-multicast-config` with the flat dict (before
    optional `rate_control`, then rate limit).
  - Reject nested wrapper key `multiCast` with an actionable error (PATCH body is flat, not GET-shaped).
- Require `multicast_config` on `update_multicast_config(...)` (no default guest preset; param name matches `create()`).
- **Remove** `guest_multicast_filter` from `create()` and **remove** `build_guest_multicast_setting()` from the SDK.
- **Do not** add SDK multicast preset builders; StackStorm pack and README document `GUEST_MULTICAST` / `SECURED_MULTICAST`
  dicts aligned with `docs/wlan_samples`.

### Consequences
- Callers own multicast preset dicts (guest filter + `filterMode` 15; secured `arpCastEnable` with `filterEnable` false).
- Breaking change for `guest_multicast_filter` and `build_guest_multicast_setting` consumers.
- `filterMode` is a bitmask (IGMP=1, mDNS=2, Others=4); document in README.

---

## Decision 23 (2026-05): Wi-Fi create type `guest` renamed to `open-isolated`

### Context
`type="guest"` on `WiFiNetworksResource.create()` mapped to open + `guestNetEnable=True` (client isolation), which
collided with Omada “guest” terminology and diverged from the cross-vendor wif-services schema (`open-isolated` in
StackStorm / Ruckus automation).

### Decision
- Replace supported create type `guest` with `open-isolated` (same Omada payload: `security=0`, default `guestNetEnable=True`).
- **Do not** accept `type="guest"` as a deprecated alias.

### Consequences
- Breaking change for callers using `type="guest"`; migrate to `type="open-isolated"`.
- Aligns Omada SDK string types with wif-services / `create_and_activate_wifi_network` schema naming.

---

## Decision 24 (2026-05): PPSK profile lookup by name on `ppsk_local` create

### Context
`type="ppsk_local"` create requires a PPSK profile id in `ppskSetting.ppskProfileId`. Callers (StackStorm, NetBox-driven
automation) know the Omada **profile name** (e.g. `Services_PPSK_Profile`) but not the opaque id.

### Decision
- Replace `ppsk_profile_id` on `WiFiNetworksResource.create()` with **`ppsk_profile_name`** (breaking; no dual mode).
- Resolve name before POST: `GET /openapi/v1/sites/{siteId}/ppsk-profiles`, exact match on list item `profileName`, use `id`.
- **0 matches:** `ValueError` with profile name and site id.
- **>1 matches:** `ValueError` (defensive).
- Keep internal `_build_ppsk_local_setting(ppsk_profile_id=...)` unchanged (resolved Omada id).

### Consequences
- Corporate/resident automation passes human-readable profile names aligned with Omada UI.
- Extra GET on every `ppsk_local` create that uses `ppsk_profile_name`.
- Callers using `ppsk_profile_id` must migrate to `ppsk_profile_name`.

---

## Decision 25 (2026-05): RADIUS profile lookup by name on `dpsk` create

### Context
`type="dpsk"` create requires a RADIUS profile id in `ppskSetting.radiusProfileId`. Callers (StackStorm, NetBox-driven
automation) know the Omada **profile name** (e.g. `Home Networking Wi-Fi`) but not the opaque id. Decision 24 left RADIUS
lookup out of scope.

### Decision
- Replace `radius_profile_id` on `WiFiNetworksResource.create()` with **`radius_profile_name`** (breaking; no dual mode).
- Resolve name before POST: `GET /openapi/v1/sites/{siteId}/profiles/radius`, exact match on list item `name`, use
  `radiusProfileId`.
- **0 matches:** `ValueError` with profile name and site id.
- **>1 matches:** `ValueError` listing conflicting `radiusProfileId`s.
- `nas_id` remains required when `radius_profile_name` is set.
- Keep internal `_build_dpsk_radius_setting(radius_profile_id=...)` unchanged (resolved Omada id).

### Consequences
- Resident automation passes human-readable RADIUS profile names aligned with Omada UI.
- Extra GET on every `dpsk` create that uses `radius_profile_name`.
- Callers using `radius_profile_id` must migrate to `radius_profile_name`.

---

## Decision 26 (2026-05): Wi-Fi SSID `create` post-create PATCH failures raise `WiFiNetworkPartiallyConfiguredError`

### Context
`create()` is not atomic: it POSTs the SSID, then performs up to three optional PATCHes
(`update-multicast-config`, `update-rate-control`, `update-rate-limit`; Decisions 20/21/22). If a PATCH
fails after a successful POST, the SSID already exists on the controller. Previously the underlying
exception propagated as-is, discarding the created `ssidId` — callers could not tell the SSID had been
created, retry the failed step, or delete it without a name lookup.

### Decision
- Add exception `WiFiNetworkPartiallyConfiguredError(OmadaAPIError)` carrying `ssid_id`, `failed_step`
  (`update-multicast-config` / `update-rate-control` / `update-rate-limit`), and `completed_steps`.
- In `create()`, wrap the post-create PATCH block: on any failure after the POST, raise
  `WiFiNetworkPartiallyConfiguredError` with the created `ssid_id` and the failed/completed steps; the
  original error (HTTP `OmadaAPIError` or a `ValueError` from a profile-name lookup) is preserved as `__cause__`.
- Validate `multicast_config` / `rate_control` shape and `rate_limit_profile_name` non-emptiness **before**
  the POST: a malformed input raises `ValueError` without creating an SSID (a usage error, not a partial
  configuration). Only failures after a successful POST become `WiFiNetworkPartiallyConfiguredError`.
- POST failures are unchanged (no SSID created, the underlying error propagates directly).
- Export the exception from `omada_client`.

### Consequences
- `create()` callers can catch `WiFiNetworkPartiallyConfiguredError` to retry the failed step or delete the
  partially configured SSID by `ssid_id`, instead of losing the id behind an opaque error.
- It subclasses `OmadaAPIError`, so existing broad `except OmadaAPIError` handlers still catch it.
- A successful `create()` return value is unchanged (raw POST response); surfacing `ssidId` on success is
  out of scope here.
