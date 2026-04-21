# ADR: Architecture decisions (single-file ADR log)

## Status
Accepted

## ADR file convention
This repository maintains ADR decisions in a single evolving file (`docs/adr.md`) rather than creating a new ADR file per decision.

---

## Decision A (2026-04): Hand-written client with patched OpenAPI and internal generated models

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

## Decision B (2026-04): Align local spec patches with upstream `omada-go-sdk` conventions

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

## Decision C (2026-04): Local-controller-only API contract

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
