# Controller behaviour notes

Behaviours observed on a **live Omada controller** that diverge from the published
Open API spec. These are the discrepancies this SDK works around or documents; they
double as feedback evidence for TP-Link.

Unless noted otherwise, observations are from controller **6.2.0.17** (apiVer 3) with
switch **SG2210XMP-M2** firmware **1.0.26**, verified 2026-07-08. Behaviour can change
across controller and firmware upgrades, so entries are dated where they are
version-specific.

## LAN-profile `poe` enum is inverted

The `poe` field on the LAN switch profile has its `0`/`1` values inverted relative to
the vendor's published description (and relative to the port-level `poe` field):

- LAN profile `poe`: `0` = off, `1` = on, `2` = do-not-modify.
- Port-level `OswPortSettingVO.poe`: `0` = off, `1` = on.

The published spec described the LAN-profile enum as `0: on, 1: off`. The SDK corrects
the description via a local spec patch.

## DHCP snooping — create requires a `devices` envelope

`POST` to create DHCP-snoop entries is documented as taking a flat object, but the
controller requires a device-keyed envelope:

```json
{ "devices": [ { "mac": "…", "ports": [ { "port": N } ] } ] }
```

Sending the flat/bare object returns `errorCode 0` ("success") but **persists nothing**
— a silent no-op. Reads must confirm persistence rather than trusting the return code.

Additional shape requirements:

- `standardPort` must be sent as a **string** (`"unit/slot/port"`); the object form the
  read-back returns is rejected with HTTP `400` on write.

## Per-port `dhcpSnoopEnable` is a silent no-op

Setting `OswPortSettingVO.dhcpSnoopEnable` per port returns `errorCode 0` but is never
persisted (echoed back unchanged) on controller 6.2.0.17. Per-port DHCP-snoop enable is
not writable through this path.

## dot1x switch-setting fields — now optional (firmware-resolved)

The dot1x switch-setting entry fields `type`, `selected`, `singleMabAuthPorts` (per
entry) and the top-level `resource` field were **previously required** — the controller
returned "Invalid request parameters" when they were absent. As of controller 6.2.0.17 /
firmware 1.0.26 they are **optional**: a minimal `{ mac, dot1xPorts, mabPorts }` entry
now persists. These fields are absent from the controller's own fetched spec, so the SDK
does not add them.

Related: the global `mab` flag no longer gates `mabPorts` — a port can be added to
`mabPorts` with `mab: false`.

## authType 3 ("Both") is not reachable via the Open API

The controller UI offers a "Both" 802.1X/MAB port mode that reads back as `authType 3`.
It is not reachable through the Open API write path: putting a port in both `dot1xPorts`
and `mabPorts` is rejected with "Invalid request parameters". The UI sets it via an
internal (non-Open-API) endpoint.
