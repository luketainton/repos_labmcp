"""MCP tool provider for Pushover's Message API."""

from collections.abc import Sequence
from typing import Any

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from .clients import ServiceClient, ServiceClientFactory
from .config import Settings


class PushoverClient(ServiceClient):
    """Client which keeps Pushover credentials in server-side form data."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings.pushover_api_url, None, settings.http_timeout)
        self._app_token = (
            settings.pushover_app_token.get_secret_value() if settings.pushover_app_token else None
        )
        self._user_key = (
            settings.pushover_user_key.get_secret_value() if settings.pushover_user_key else None
        )

    async def send_notification(self, payload: dict[str, Any]) -> Any:
        """Send a form-encoded notification without exposing credentials to MCP callers."""
        if not self._app_token or not self._user_key:
            raise RuntimeError(
                "Pushover is not configured. Set PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY."
            )
        return await self.request(
            "POST",
            "/1/messages.json",
            data={"token": self._app_token, "user": self._user_key, **payload},
        )


def pushover_client(settings: Settings) -> PushoverClient:
    """Create a client for Pushover's Message API."""
    return PushoverClient(settings)


class PushoverOperationProvider(Provider):
    """Expose Pushover's documented message-send endpoint as an MCP tool."""

    def __init__(self, client_factory: ServiceClientFactory, auth: Any = None) -> None:
        super().__init__()
        self._tools = (_make_send_notification_tool(client_factory, auth),)

    async def _list_tools(self) -> Sequence[Tool]:
        return self._tools


def _make_send_notification_tool(client_factory: ServiceClientFactory, auth: Any) -> Tool:
    async def execute(
        message: str,
        title: str | None = None,
        device: str | None = None,
        priority: int | None = None,
        sound: str | None = None,
        url: str | None = None,
        url_title: str | None = None,
        html: bool | None = None,
        timestamp: int | None = None,
        ttl: int | None = None,
        retry: int | None = None,
        expire: int | None = None,
    ) -> Any:
        """Send a Pushover notification using server-configured credentials."""
        if not message.strip():
            raise ValueError("message must not be empty")
        if priority is not None and priority not in {-2, -1, 0, 1, 2}:
            raise ValueError("priority must be one of -2, -1, 0, 1, or 2")
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be positive")
        if priority == 2 and (retry is None or expire is None):
            raise ValueError("emergency priority requires retry and expire")
        if retry is not None and retry < 30:
            raise ValueError("retry must be at least 30 seconds")
        if expire is not None and not 1 <= expire <= 10800:
            raise ValueError("expire must be between 1 and 10800 seconds")
        payload = {
            name: value
            for name, value in {
                "message": message,
                "title": title,
                "device": device,
                "priority": priority,
                "sound": sound,
                "url": url,
                "url_title": url_title,
                "html": 1 if html else None,
                "timestamp": timestamp,
                "ttl": ttl,
                "retry": retry,
                "expire": expire,
            }.items()
            if value is not None
        }
        return await client_factory().send_notification(payload)  # type: ignore[attr-defined]

    return Tool.from_function(
        execute,
        name="pushover_send_notification",
        description="Send a Pushover notification. Credentials are configured only on the server.",
        auth=auth,
    )
