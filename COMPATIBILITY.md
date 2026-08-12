# Compatibility

This matrix records which versions of this SDK have been verified against which
Omada controller versions and switch/AP firmware, on real hardware.

The Omada Open API is effectively unversioned (`info.version` is `v0.1` on both
the cloud spec and a controller's `/v3/api-docs`), so compatibility is anchored to
the **controller version** (`controllerVer`) + **API version** (`apiVer`) reported
by the controller `/api/info` endpoint, plus the tested device model and firmware.

| SDK | controllerVer | apiVer | Device | Firmware | Result | Date |
|-----|---------------|--------|--------|----------|--------|------|
| 1.3.0 | 6.2.0.17 | 3 | SG2210XMP-M2 | 1.0.26 | ✅ pass | 2026-07-08 |
| 1.4.0 | 6.2.10.17 | 3 | SG2210XMP-M2 v1.0 | 1.0.26 | ✅ pass | 2026-07-08 |
| 1.5.0 | 6.2.14.11 | 3 | SG2210XMP-M2 v1.0 | 1.0.26 | ✅ pass | 2026-08-12 |

The current SDK release **v1.5.0** is verified against controller `6.2.14.11`.

## Capability notes

- LAN-profile `poe` enum is inverted relative to the port-level `poe` field — see
  [docs/controller-behaviour-notes.md](docs/controller-behaviour-notes.md).
- DHCP-snooping create requires a `{"devices": [...]}` envelope; sending a bare
  object reports success but persists nothing.
- Some documented dot1x switch-setting fields are optional as of controller
  6.2.0.17 / firmware 1.0.26.

Full behaviour details: [docs/controller-behaviour-notes.md](docs/controller-behaviour-notes.md)
(machine-readable rows in [compatibility.json](compatibility.json)).

## Maintenance

Rows are added as a release-checklist step: before tagging an SDK release, verify it
against the target controller version(s) on real hardware and add a row here and to
`compatibility.json`. Re-verify after any controller or switch/AP firmware upgrade.
