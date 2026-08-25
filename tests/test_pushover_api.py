from types import SimpleNamespace

import pytest

from labmcp.pushover_api import PushoverClient, PushoverOperationProvider


class FakeClient:
    def __init__(self) -> None:
        self.payloads = []

    async def send_notification(self, payload):
        self.payloads.append(payload)
        return {"status": 1}


@pytest.mark.asyncio
async def test_send_notification_uses_only_non_empty_optional_values() -> None:
    client = FakeClient()
    provider = PushoverOperationProvider(lambda: client)
    tool = (await provider.list_tools())[0]

    result = await tool.fn(message="Backup complete", title="Lab", html=True, priority=1)

    assert result == {"status": 1}
    assert client.payloads == [
        {"message": "Backup complete", "title": "Lab", "html": 1, "priority": 1}
    ]


@pytest.mark.asyncio
async def test_send_notification_rejects_empty_message() -> None:
    provider = PushoverOperationProvider(lambda: FakeClient())
    tool = (await provider.list_tools())[0]

    with pytest.raises(ValueError, match="message must not be empty"):
        await tool.fn(message="  ")


@pytest.mark.asyncio
async def test_emergency_priority_requires_valid_retry_and_expiry() -> None:
    provider = PushoverOperationProvider(lambda: FakeClient())
    tool = (await provider.list_tools())[0]

    with pytest.raises(ValueError, match="requires retry and expire"):
        await tool.fn(message="Urgent", priority=2)

    with pytest.raises(ValueError, match="at least 30"):
        await tool.fn(message="Urgent", priority=2, retry=29, expire=60)


@pytest.mark.asyncio
async def test_client_adds_credentials_only_to_form_data(monkeypatch) -> None:
    settings = SimpleNamespace(
        pushover_api_url="https://api.pushover.net",
        http_timeout=20.0,
        pushover_app_token=SimpleNamespace(get_secret_value=lambda: "app-token"),
        pushover_user_key=SimpleNamespace(get_secret_value=lambda: "user-key"),
    )
    client = PushoverClient(settings)
    calls = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"status": 1}

    monkeypatch.setattr(client, "request", request)

    assert await client.send_notification({"message": "hello"}) == {"status": 1}
    assert calls == [
        (
            "POST",
            "/1/messages.json",
            {"data": {"token": "app-token", "user": "user-key", "message": "hello"}},
        )
    ]
