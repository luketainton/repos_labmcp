"""LabMCP server and its per-service HTTP applications."""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.applications import Starlette
from starlette.routing import Mount

from .action1_api import Action1OperationProvider
from .auth import NETWORK_TRANSPORTS, create_auth_provider, ensure_network_transport_is_authenticated
from .authorization import require_service_access
from .clients import action1_client, gitea_client, n8n_client, pangolin_client, pocket_id_client, shlink_client
from .config import Settings, get_settings
from .gitea_api import GiteaOperationProvider
from .n8n_api import N8NOperationProvider
from .pangolin_api import PangolinOperationProvider
from .pocket_id_api import PocketIDOperationProvider
from .pushover_api import PushoverOperationProvider, pushover_client
from .shlink_api import ShlinkOperationProvider
from .tool_logging import ToolCallLoggingMiddleware
from .version import get_version


# Keep the legacy aggregate catalogue at /mcp, but give clients an endpoint whose
# action list contains only the application they are connecting to.
SERVICE_PATHS = {
    "gitea": "gitea",
    "pocketid": "pocket_id",
    "n8n": "n8n",
    "pangolin": "pangolin",
    "shlink": "shlink",
    "action1": "action1",
    "pushover": "pushover",
}


def _service_auth(service: str, settings: Settings):
    return require_service_access(service, settings)


def _path_settings(settings: Settings, path: str) -> Settings:
    """Return settings whose OAuth resource is the mounted application URL."""
    base_url = settings.mcp_auth_base_url
    if not base_url:
        return settings
    # ``http_app(path='/')`` serves the mounted endpoint with a trailing slash.
    # In direct JWT mode the endpoint is also the token audience. OIDC proxy
    # mode instead validates upstream tokens against its registered client ID.
    resource_url = f"{base_url.rstrip('/')}/{path}/"
    update: dict[str, str] = {"mcp_auth_base_url": resource_url}
    if settings.mcp_auth_mode == "jwt":
        update["mcp_auth_jwt_audience"] = resource_url
    return settings.model_copy(update=update)


def _providers_for(service: str, settings: Settings) -> list[Any]:
    if service == "gitea":
        return [GiteaOperationProvider(lambda: gitea_client(get_settings()), _service_auth(service, settings))]
    if service == "pocket_id":
        return [PocketIDOperationProvider(lambda: pocket_id_client(get_settings()), _service_auth(service, settings))]
    if service == "n8n":
        return [N8NOperationProvider(lambda: n8n_client(get_settings()), api_path=settings.n8n_api_path, auth=_service_auth(service, settings))]
    if service == "pangolin":
        return [PangolinOperationProvider(lambda: pangolin_client(get_settings()), api_path=settings.pangolin_api_path, auth=_service_auth(service, settings))]
    if service == "shlink":
        return [ShlinkOperationProvider(lambda: shlink_client(get_settings()), api_version=settings.shlink_api_version, auth=_service_auth(service, settings))]
    if service == "pushover":
        return [PushoverOperationProvider(lambda: pushover_client(get_settings()), _service_auth(service, settings))]
    if service == "action1":
        return [Action1OperationProvider(lambda: action1_client(settings), _service_auth(service, settings))]
    raise ValueError(f"Unknown LabMCP service: {service}")


def _add_common_tools(app: FastMCP) -> None:
    app.tool(
        labmcp_get_version,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    )


def _add_gitea_tools(app: FastMCP, settings: Settings) -> None:
    auth = _service_auth("gitea", settings)
    for tool, annotations in (
        (gitea_list_repositories, ToolAnnotations(readOnlyHint=True, openWorldHint=True)),
        (gitea_get_repository, ToolAnnotations(readOnlyHint=True, openWorldHint=True)),
        (gitea_list_issues, ToolAnnotations(readOnlyHint=True, openWorldHint=True)),
        (gitea_create_issue, ToolAnnotations(readOnlyHint=False, openWorldHint=True)),
    ):
        app.tool(tool, annotations=annotations, auth=auth)


def _add_pocket_id_tools(app: FastMCP, settings: Settings) -> None:
    auth = _service_auth("pocket_id", settings)
    for tool in (pocket_id_openid_configuration, pocket_id_health):
        app.tool(tool, annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True), auth=auth)


def create_mcp(settings: Settings, service: str | None = None) -> FastMCP:
    """Create either the legacy full catalogue or one service-specific catalogue."""
    selected_services = tuple(SERVICE_PATHS.values()) if service is None else (service,)
    app = FastMCP(
        f"Home Lab ({get_version()})",
        auth=create_auth_provider(settings),
        providers=[provider for name in selected_services for provider in _providers_for(name, settings)],
    )
    app.add_middleware(ToolCallLoggingMiddleware())
    _add_common_tools(app)
    if service in (None, "gitea"):
        _add_gitea_tools(app, settings)
    if service in (None, "pocket_id"):
        _add_pocket_id_tools(app, settings)
    return app


def create_network_app(settings: Settings) -> Starlette:
    """Create one ASGI process with the legacy and per-service MCP paths mounted."""
    mounted_apps = [("mcp", create_mcp(_path_settings(settings, "mcp")))]
    mounted_apps.extend(
        (path, create_mcp(_path_settings(settings, path), service))
        for path, service in SERVICE_PATHS.items()
    )
    http_apps = [
        (path, app.http_app(path="/", transport=settings.mcp_transport))
        for path, app in mounted_apps
    ]

    @asynccontextmanager
    async def lifespan(_: Starlette):
        async with AsyncExitStack() as stack:
            for _, app in http_apps:
                await stack.enter_async_context(app.lifespan(app))
            yield

    return Starlette(
        routes=[Mount(f"/{path}", app=app) for path, app in http_apps], lifespan=lifespan
    )


async def gitea_list_repositories(page: int = 1, limit: int = 50, *, private: bool | None = None) -> list[dict[str, Any]]:
    """List repositories visible to the configured Gitea token."""
    if page < 1 or not 1 <= limit <= 100:
        raise ValueError("page must be positive and limit must be between 1 and 100")
    params: dict[str, Any] = {"page": page, "limit": limit}
    if private is not None:
        params["private"] = private
    return await gitea_client(get_settings()).request("GET", "/api/v1/user/repos", params=params)


async def gitea_get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get metadata for one Gitea repository."""
    return await gitea_client(get_settings()).request("GET", f"/api/v1/repos/{owner}/{repo}")


async def gitea_list_issues(owner: str, repo: str, state: str = "open", page: int = 1, limit: int = 50) -> list[dict[str, Any]]:
    """List issues for a Gitea repository."""
    if state not in {"open", "closed", "all"}:
        raise ValueError("state must be open, closed, or all")
    if page < 1 or not 1 <= limit <= 100:
        raise ValueError("page must be positive and limit must be between 1 and 100")
    return await gitea_client(get_settings()).request("GET", f"/api/v1/repos/{owner}/{repo}/issues", params={"state": state, "page": page, "limit": limit})


async def gitea_create_issue(owner: str, repo: str, title: str, body: str = "") -> dict[str, Any]:
    """Create an issue in a Gitea repository."""
    if not title.strip():
        raise ValueError("title must not be empty")
    return await gitea_client(get_settings()).request("POST", f"/api/v1/repos/{owner}/{repo}/issues", json={"title": title, "body": body})


async def pocket_id_openid_configuration() -> dict[str, Any]:
    """Read Pocket ID's OpenID Connect discovery document."""
    return await pocket_id_client(get_settings()).request("GET", "/.well-known/openid-configuration")


async def pocket_id_health() -> Any:
    """Check Pocket ID health using POCKET_ID_HEALTH_PATH (default: /api/health)."""
    settings = get_settings()
    return await pocket_id_client(settings).request("GET", settings.pocket_id_health_path)


def labmcp_get_version() -> str:
    """Return the running labmcp package version."""
    return get_version()


_settings = get_settings()
mcp = create_mcp(_settings)


def main() -> None:
    settings = get_settings()
    ensure_network_transport_is_authenticated(settings)
    if settings.mcp_transport not in NETWORK_TRANSPORTS:
        mcp.run(transport=settings.mcp_transport, host=settings.mcp_host, port=settings.mcp_port)
        return
    import uvicorn

    uvicorn.run(create_network_app(settings), host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
