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
