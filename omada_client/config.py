"""Endpoint configuration helpers for local controller access."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OmadaEndpointConfig:
    api_base_url: str
    token_url: str


def resolve_endpoint_config(
    base_url: str,
    token_url: str | None = None,
) -> OmadaEndpointConfig:
    resolved_base_url = base_url.rstrip("/")
    if not resolved_base_url:
        raise ValueError("base_url is required")
    resolved_token_url = token_url or f"{resolved_base_url}/openapi/authorize/token"
    return OmadaEndpointConfig(api_base_url=resolved_base_url, token_url=resolved_token_url)
