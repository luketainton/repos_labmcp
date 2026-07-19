from typing import Any

from fastmcp import FastMCP

from .auth import create_auth_provider, ensure_network_transport_is_authenticated
from .authorization import require_service_access
from .clients import gitea_client, pocket_id_client
from .config import get_settings
from .gitea_api import call_operation as call_gitea_operation
from .gitea_api import list_operations as list_gitea_operations
from .pocket_id_api import call_operation, list_operations
from .version import get_version

_settings = get_settings()
mcp = FastMCP(f"Home Lab ({get_version()})", auth=create_auth_provider(_settings))


def _service_auth(service: str):
    return require_service_access(service, _settings)


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


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_list_api_operations(refresh: bool = False) -> list[dict[str, str]]:
    """List validated Gitea Swagger operations, methods, paths, and body encoding.

    The operation registry is read from the configured Gitea instance and cached.
    Set refresh=true after upgrading Gitea to reload its Swagger document.
    """
    return await list_gitea_operations(gitea_client(get_settings()), refresh=refresh)


@mcp.tool(auth=_service_auth("gitea"))
async def gitea_call_api(
    operation: str,
    *,
    path_params: dict[str, str] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
    form: dict[str, Any] | None = None,
) -> Any:
    """Call a documented Gitea JSON/form operation by its Swagger operation ID.

    Use gitea_list_api_operations first. Binary file upload/download endpoints are
    excluded because they require an MCP attachment interface.
    """
    return await call_gitea_operation(
        gitea_client(get_settings()),
        operation,
        path_params=path_params,
        query=query,
        body=body,
        form=form,
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


@mcp.tool(auth=_service_auth("pocket_id"))
def pocket_id_list_api_operations() -> list[dict[str, str]]:
    """List validated Pocket ID API operations, methods, paths, and body encoding."""
    return list_operations()


@mcp.tool(auth=_service_auth("pocket_id"))
async def pocket_id_call_api(
    operation: str,
    *,
    path_params: dict[str, str] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
    form: dict[str, str] | None = None,
) -> Any:
    """Call a documented Pocket ID JSON/form API operation by its validated name.

    Use pocket_id_list_api_operations first to discover operation names and paths.
    This supports all documented non-binary operations; image upload/download endpoints
    are excluded because they require an attachment interface.
    """
    return await call_operation(
        pocket_id_client(get_settings()),
        operation,
        path_params=path_params,
        query=query,
        body=body,
        form=form,
    )


def main() -> None:
    settings = get_settings()
    ensure_network_transport_is_authenticated(settings)
    mcp.run(transport=settings.mcp_transport, host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
