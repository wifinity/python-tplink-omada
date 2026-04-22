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

### Local Controller Mode

Local-controller mode requires:

- `base_url` pointing to the controller host.
- `omadac_id` matching the controller identifier.
- Token exchange through `POST /openapi/authorize/token` using query `grant_type=client_credentials`.
- JSON token payload fields: `omadacId`, `client_id`, `client_secret`.
- API authentication header format: `Authorization: AccessToken=<token>`.

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
