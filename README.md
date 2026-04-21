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

site = client.sites.create(name="Main Site")
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

### Local Controller Mode

Local-controller mode requires:

- `base_url` pointing to the controller host.
- `omadac_id` matching the controller identifier.
- Token exchange through `POST /openapi/authorize/token` using query `grant_type=client_credentials`.
- JSON token payload fields: `omadacId`, `client_id`, `client_secret`.
- API authentication header format: `Authorization: AccessToken=<token>`.

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
