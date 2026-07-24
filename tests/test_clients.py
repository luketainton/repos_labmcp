from types import SimpleNamespace

import httpx
import pytest
from fastmcp.exceptions import ToolError

from labmcp.clients import ServiceClient, gitea_client, pocket_id_client


class RecordingAsyncClient:
    response_kwargs = {"json": {"ok": True}}
    requests: list[dict] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return httpx.Response(
            200,
            request=httpx.Request(method, url),
            **self.response_kwargs,
        )


@pytest.fixture(autouse=True)
def clear_recorded_requests():
    RecordingAsyncClient.requests.clear()


@pytest.mark.asyncio
async def test_service_client_builds_url_and_returns_json(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", RecordingAsyncClient)
    client = ServiceClient("https://service.example/", "secret", 5.0, auth_prefix="token")

    result = await client.request("GET", "/api/status", params={"page": 1})

    assert result == {"ok": True}
    assert RecordingAsyncClient.requests == [
        {
            "method": "GET",
            "url": "https://service.example/api/status",
            "params": {"page": 1},
            "json": None,
            "headers": {"Accept": "application/json", "Authorization": "token secret"},
        }
    ]


@pytest.mark.asyncio
async def test_service_client_returns_text_for_non_json_response(monkeypatch):
    class TextClient(RecordingAsyncClient):
        response_kwargs = {"text": "healthy"}

    monkeypatch.setattr(httpx, "AsyncClient", TextClient)

    result = await ServiceClient("https://service.example", None, 5.0).request("GET", "/health")

    assert result == {"status_code": 200, "text": "healthy"}


@pytest.mark.asyncio
async def test_service_client_surfaces_upstream_error_details_to_tools(monkeypatch):
    class ConflictClient(RecordingAsyncClient):
        async def request(self, method, url, **kwargs):
            self.requests.append({"method": method, "url": url, **kwargs})
            return httpx.Response(
                409,
                request=httpx.Request(method, url),
                json={"message": "pull request is not mergeable"},
            )

    monkeypatch.setattr(httpx, "AsyncClient", ConflictClient)

    with pytest.raises(
        ToolError,
        match=r"POST /api/v1/repos/alice/notes/pulls/7/merge failed with 409: .*not mergeable",
    ):
        await ServiceClient("https://service.example", None, 5.0).request(
            "POST", "/api/v1/repos/alice/notes/pulls/7/merge", json={"Do": "merge"}
        )


def test_service_clients_use_service_specific_auth_headers():
    settings = SimpleNamespace(
        gitea_url="https://gitea.example",
        gitea_token=SimpleNamespace(get_secret_value=lambda: "gitea-secret"),
        pocket_id_url="https://pocket.example",
        pocket_id_token=SimpleNamespace(get_secret_value=lambda: "pocket-secret"),
        http_timeout=10.0,
    )

    gitea = gitea_client(settings)
    pocket_id = pocket_id_client(settings)

    assert (gitea.auth_header, gitea.auth_prefix, gitea.token) == (
        "Authorization",
        "token",
        "gitea-secret",
    )
    assert (pocket_id.auth_header, pocket_id.auth_prefix, pocket_id.token) == (
        "X-API-KEY",
        "",
        "pocket-secret",
    )


def test_service_client_requires_a_base_url():
    with pytest.raises(RuntimeError, match="not configured"):
        ServiceClient(None, None, 5.0)._url("/health")
