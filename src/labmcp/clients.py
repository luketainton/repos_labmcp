from collections.abc import Callable, Mapping
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from .config import Settings

ServiceClientFactory = Callable[[], "ServiceClient"]


class ServiceClient:
    def __init__(
        self,
        base_url: str | None,
        token: str | None,
        timeout: float,
        auth_header: str = "Authorization",
        auth_prefix: str = "Bearer",
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.token = token
        self.timeout = timeout
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix

    def _url(self, path: str) -> str:
        if not self.base_url:
            raise RuntimeError(
                "This service is not configured. Set its *_URL environment variable."
            )
        return f"{self.base_url}/{path.lstrip('/')}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self.token:
            headers[self.auth_header] = (
                f"{self.auth_prefix} {self.token}" if self.auth_prefix else self.token
            )
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            request_kwargs: dict[str, Any] = {
                "params": params,
                "json": json,
                "headers": headers,
            }
            if data is not None:
                request_kwargs["data"] = data
            response = await client.request(method, self._url(path), **request_kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500]
            # FastMCP deliberately masks ordinary exceptions when configured to
            # do so.  Raise its explicit tool error type so an upstream API
            # diagnostic remains available to the caller.
            raise ToolError(
                f"{method} {path} failed with {response.status_code}: {detail}"
            ) from exc
        if not response.content:
            return {"status_code": response.status_code}
        try:
            return response.json()
        except ValueError:
            return {"status_code": response.status_code, "text": response.text}


def gitea_client(settings: Settings) -> ServiceClient:
    token = settings.gitea_token.get_secret_value() if settings.gitea_token else None
    return ServiceClient(settings.gitea_url, token, settings.http_timeout, auth_prefix="token")


def pocket_id_client(settings: Settings) -> ServiceClient:
    token = settings.pocket_id_token.get_secret_value() if settings.pocket_id_token else None
    return ServiceClient(
        settings.pocket_id_url,
        token,
        settings.http_timeout,
        auth_header="X-API-KEY",
        auth_prefix="",
    )


def n8n_client(settings: Settings) -> ServiceClient:
    """Create a client for n8n's API-key authenticated REST API."""
    token = settings.n8n_api_key.get_secret_value() if settings.n8n_api_key else None
    return ServiceClient(
        settings.n8n_url,
        token,
        settings.http_timeout,
        auth_header="X-N8N-API-KEY",
        auth_prefix="",
    )
