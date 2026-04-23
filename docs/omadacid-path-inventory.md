# `{omadacId}` Path Inventory (Fixed Spec)

Source: `spec/fixed/all-fixed.json`

## Extracted inventory scope

- Total paths containing `{omadacId}`: 1609
- Primary implemented prefix family: `/openapi/v1/{omadacId}/sites/...`

## Mapping to currently implemented resources

- `SitesResource.create`
  - SDK path template: `/openapi/v1/sites`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites`
  - Fixed spec match: exact
- `DevicesResource.list`, `DevicesResource.create`/`DevicesResource.register`, `DevicesResource.remove`
  - SDK path template: `/openapi/v1/sites/{siteId}/devices`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/devices`
  - Fixed spec match: exact
- `DevicesResource.get_by_mac` (AP-specific)
  - SDK path template: `/openapi/v1/sites/{siteId}/aps/{apMac}`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/aps/{apMac}`
  - Fixed spec match: exact
- `DevicesResource.delete` (forget by MAC)
  - SDK path template: `/openapi/v1/sites/{siteId}/devices/{deviceMac}/forget`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceMac}/forget`
  - Fixed spec match: exact
- `DevicesResource.add_by_device_key`
  - SDK path template: `/openapi/v1/sites/{siteId}/multi-devices/devicekey-add`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/multi-devices/devicekey-add`
  - Fixed spec match: exact
- `DevicesResource.send_config`
  - SDK path template: `/openapi/v1/sites/{siteId}/devices/{deviceId}/config`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceId}/config`
  - Fixed spec match: no exact `.../config` route in current fixed spec; device-specific routes are present under `/openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceMac}/...`
- `DevicesResource.status`
  - SDK path template: `/openapi/v1/sites/{siteId}/devices/{deviceId}/status`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/devices/{deviceId}/status`
  - Fixed spec match: no exact `.../status` route in current fixed spec; related operational status routes are present under the same device subtree
- `WiFiNetworksResource.create`
  - SDK path template: `/openapi/v1/sites/{siteId}/wlans`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/wlans`
  - Fixed spec match: no exact route; closest family in fixed spec is `/openapi/v1/{omadacId}/sites/{siteId}/wireless-network/wlans...`
- `WiFiNetworksResource.assign_to_ap_group`
  - SDK path template: `/openapi/v1/sites/{siteId}/wlans/{wlanId}/ap-groups`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/wlans/{wlanId}/ap-groups`
  - Fixed spec match: no exact route in current fixed spec
- `APGroupsResource.create`
  - SDK path template: `/openapi/v1/sites/{siteId}/ap-groups`
  - Canonical local-controller path: `/openapi/v1/{omadacId}/sites/{siteId}/ap-groups`
  - Fixed spec match: no exact route in current fixed spec

## Typed facade reuse pattern

- `APsResource` maps AP workflows onto canonical `DevicesResource` actions:
  - `APsResource.list` -> `DevicesResource.list` with AP-specific query options
  - `APsResource.get_by_mac` -> `DevicesResource.get_by_mac(..., device_type="ap")`
  - `APsResource.create` -> `DevicesResource.add_by_device_key`
  - `APsResource.delete` -> `DevicesResource.delete`
- This pattern is the expected extension model for future device-type resources (for example switches).

## Contract conclusion

All implemented resource paths must be sent through client path canonicalization so `/openapi/v1/...` routes are rewritten to `/openapi/v1/{omadacId}/...` deterministically for local-controller operation.
