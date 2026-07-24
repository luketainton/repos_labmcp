from typing import Any

from fastmcp import FastMCP

from .auth import create_auth_provider, ensure_network_transport_is_authenticated
from .authorization import require_service_access
from .clients import action1_client, gitea_client, n8n_client, pocket_id_client
from .action1_api import Action1OperationProvider
from .config import get_settings
from .gitea_api import GiteaOperationProvider
from .n8n_api import N8NOperationProvider
from .pocket_id_api import PocketIDOperationProvider
from .version import get_version

_settings = get_settings()
_action1_client = action1_client(_settings)


def _service_auth(service: str):
    return require_service_access(service, _settings)


mcp = FastMCP(
    f"Home Lab ({get_version()})",
    auth=create_auth_provider(_settings),
    providers=[
        GiteaOperationProvider(lambda: gitea_client(get_settings()), _service_auth("gitea")),
        PocketIDOperationProvider(
            lambda: pocket_id_client(get_settings()), _service_auth("pocket_id")
        ),
        N8NOperationProvider(
            lambda: n8n_client(get_settings()),
            api_path=_settings.n8n_api_path,
            auth=_service_auth("n8n"),
        ),
        Action1OperationProvider(
            lambda: _action1_client, _service_auth("action1")
        ),
    ],
)


@mcp.tool()
def labmcp_get_version() -> str:
    """Return the running labmcp package version."""
    return get_version()


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_list_repositories(
    page: int = 1,
    limit: int = 50,
    *,
    private: bool | None = None,
) -> list[dict[str, Any]]:
    """List repositories visible to the configured Gitea token."""
    if page < 1 or not 1 <= limit <= 100:
        raise ValueError("page must be positive and limit must be between 1 and 100")
    params: dict[str, Any] = {"page": page, "limit": limit}
    if private is not None:
        params["private"] = private
    result = await gitea_client(get_settings()).request("GET", "/api/v1/user/repos", params=params)
    return result


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get metadata for one Gitea repository."""
    return await gitea_client(get_settings()).request("GET", f"/api/v1/repos/{owner}/{repo}")


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    page: int = 1,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List issues for a Gitea repository."""
    if state not in {"open", "closed", "all"}:
        raise ValueError("state must be open, closed, or all")
    if page < 1 or not 1 <= limit <= 100:
        raise ValueError("page must be positive and limit must be between 1 and 100")
    return await gitea_client(get_settings()).request(
        "GET",
        f"/api/v1/repos/{owner}/{repo}/issues",
        params={"state": state, "page": page, "limit": limit},
    )


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_create_issue(owner: str, repo: str, title: str, body: str = "") -> dict[str, Any]:
    """Create an issue in a Gitea repository."""
    if not title.strip():
        raise ValueError("title must not be empty")
    return await gitea_client(get_settings()).request(
        "POST", f"/api/v1/repos/{owner}/{repo}/issues", json={"title": title, "body": body}
    )


@mcp.tool(auth=_service_auth("pocket_id"))
async def pocket_id_openid_configuration() -> dict[str, Any]:
    """Read Pocket ID's OpenID Connect discovery document."""
    return await pocket_id_client(get_settings()).request(
        "GET", "/.well-known/openid-configuration"
    )


@mcp.tool(auth=_service_auth("pocket_id"))
async def pocket_id_health() -> Any:
    """Check Pocket ID health using POCKET_ID_HEALTH_PATH (default: /api/health)."""
    settings = get_settings()
    return await pocket_id_client(settings).request("GET", settings.pocket_id_health_path)


def main() -> None:
    settings = get_settings()
    ensure_network_transport_is_authenticated(settings)
    mcp.run(transport=settings.mcp_transport, host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
