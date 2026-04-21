"""Auto-generated schema index from fixed OpenAPI spec.
Do not edit manually.
"""

SCHEMA_INDEX: dict[str, dict] = {
    "AuthorizeTokenResponse": {
        "properties": {
            "access_token": {"type": "string"},
            "expires_in": {"type": "integer"},
            "token_type": {"type": "string"},
        },
        "type": "object",
    },
    "CreateSiteResponse": {
        "additionalProperties": True,
        "properties": {"result": {"additionalProperties": True, "type": "object"}},
        "type": "object",
    },
    "DeviceStatus": {"type": "object"},
}
