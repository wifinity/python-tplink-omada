"""Site-related Omada operations."""

from __future__ import annotations

import re
from typing import Any, cast

import pycountry


class SitesResource:
    def __init__(self, client: Any) -> None:
        self.client = client

    def _path(self, path: str) -> str:
        api_path = getattr(self.client, "api_path", None)
        if callable(api_path):
            return cast(str, api_path(path))
        return path

    def _validate_region(self, region: str) -> None:
        if not isinstance(region, str) or not region.strip():
            raise ValueError("region must be a non-empty string")

        region_clean = region.strip()

        # Reject ISO country codes; Omada expects full country names.
        if re.match(r"^[A-Za-z]{2,3}$", region_clean):
            try:
                country_obj = pycountry.countries.lookup(region_clean)
                if (
                    country_obj.alpha_2.upper() == region_clean.upper()
                    or country_obj.alpha_3.upper() == region_clean.upper()
                ):
                    raise ValueError(
                        f"Country code '{region}' is not accepted. "
                        "Please use the full country name (e.g., 'United Kingdom' instead of 'GB')."
                    )
            except LookupError:
                pass

        try:
            country_obj = pycountry.countries.lookup(region_clean)
            if country_obj.name.lower() == region_clean.lower():
                return
        except LookupError:
            pass

        raise ValueError(
            f"Invalid country name '{region}'. "
            "Please use a valid full country name (e.g., 'United Kingdom', 'United States')."
        )

    def _coerce_list_response(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        result = response.get("result")
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]

        for key in ("data", "items", "result"):
            value = response.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

        return []

    def _site_list_params(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        final_params: dict[str, Any] = {"page": 1, "pageSize": 1000}
        if params:
            final_params.update(params)
        return final_params

    def all(self, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        response = self.client.get(self._path("/openapi/v1/sites"), params=self._site_list_params(params))
        return self._coerce_list_response(cast(dict[str, Any], response))

    def get(self, *, id: str | None = None, name: str | None = None) -> dict[str, Any]:
        if (id is None) == (name is None):
            raise ValueError("Provide exactly one of 'id' or 'name'")

        if id is not None:
            response = cast(dict[str, Any], self.client.get(self._path(f"/openapi/v1/sites/{id}")))
            result = response.get("result")
            if isinstance(result, dict):
                return result
            return response

        sites = self.all(params={"searchKey": name})
        exact_matches = [site for site in sites if isinstance(site.get("name"), str) and site["name"] == name]
        if not exact_matches:
            raise ValueError(f"Site with name '{name}' was not found")
        if len(exact_matches) > 1:
            raise ValueError(f"Multiple sites found with name '{name}'")
        site_id = exact_matches[0].get("siteId")
        if not isinstance(site_id, str) or not site_id:
            raise ValueError(f"Matched site '{name}' does not include a valid siteId")
        return self.get(id=site_id)

    def create(
        self,
        *,
        name: str,
        region: str = "United Kingdom",
        scenario: str = "Dormitory",
        time_zone: str = "UTC",
        device_username: str | None = None,
        device_password: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self._validate_region(region)

        payload: dict[str, Any] = {"name": name, **kwargs}
        payload["region"] = region
        payload["scenario"] = scenario
        payload["timeZone"] = time_zone

        if (device_username is None) ^ (device_password is None):
            raise ValueError("device_username and device_password must be provided together")

        if device_username is not None and device_password is not None:
            payload["deviceAccountSetting"] = {
                "username": device_username,
                "password": device_password,
            }
        elif payload.get("deviceAccountSetting") is None:
            raise ValueError(
                "deviceAccountSetting is required; provide device_username and "
                "device_password or pass deviceAccountSetting in kwargs"
            )

        response = self.client.post(self._path("/openapi/v1/sites"), json=payload)
        return cast(dict[str, Any], response)
