"""Validated access to Shlink's documented REST API operations."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from .clients import ServiceClient, ServiceClientFactory
from .tool_annotations import api_operation_annotations


@dataclass(frozen=True)
class ShlinkOperation:
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str


# Generated from Shlink's current OpenAPI specification. Public redirect and
# tracking endpoints are intentionally excluded: this provider manages Shlink.
OPERATIONS: dict[str, ShlinkOperation] = {
    "list_short_urls": ShlinkOperation("GET", "/rest/v{version}/short-urls"),
    "create_short_url": ShlinkOperation("POST", "/rest/v{version}/short-urls"),
    "create_short_url_from_query": ShlinkOperation("GET", "/rest/v{version}/short-urls/shorten"),
    "parse_short_code": ShlinkOperation("GET", "/rest/v{version}/short-urls/{shortCode}"),
    "delete_short_url": ShlinkOperation("DELETE", "/rest/v{version}/short-urls/{shortCode}"),
    "edit_short_url": ShlinkOperation("PATCH", "/rest/v{version}/short-urls/{shortCode}"),
    "list_short_url_redirect_rules": ShlinkOperation(
        "GET", "/rest/v{version}/short-urls/{shortCode}/redirect-rules"
    ),
    "set_short_url_redirect_rules": ShlinkOperation(
        "POST", "/rest/v{version}/short-urls/{shortCode}/redirect-rules"
    ),
    "list_tags": ShlinkOperation("GET", "/rest/v{version}/tags"),
    "rename_tag": ShlinkOperation("PUT", "/rest/v{version}/tags"),
    "delete_tags": ShlinkOperation("DELETE", "/rest/v{version}/tags"),
    "get_tags_stats": ShlinkOperation("GET", "/rest/v{version}/tags/stats"),
    "get_visits": ShlinkOperation("GET", "/rest/v{version}/visits"),
    "list_short_url_visits": ShlinkOperation(
        "GET", "/rest/v{version}/short-urls/{shortCode}/visits"
    ),
    "delete_short_url_visits": ShlinkOperation(
        "DELETE", "/rest/v{version}/short-urls/{shortCode}/visits"
    ),
    "list_tag_visits": ShlinkOperation("GET", "/rest/v{version}/tags/{tag}/visits"),
    "list_domain_visits": ShlinkOperation("GET", "/rest/v{version}/domains/{domain}/visits"),
    "list_orphan_visits": ShlinkOperation("GET", "/rest/v{version}/visits/orphan"),
    "delete_orphan_visits": ShlinkOperation("DELETE", "/rest/v{version}/visits/orphan"),
    "list_non_orphan_visits": ShlinkOperation("GET", "/rest/v{version}/visits/non-orphan"),
    "list_domains": ShlinkOperation("GET", "/rest/v{version}/domains"),
    "set_domain_redirects": ShlinkOperation("PATCH", "/rest/v{version}/domains/redirects"),
    "get_mercure_info": ShlinkOperation("GET", "/rest/v{version}/mercure-info"),
    "health": ShlinkOperation("GET", "/rest/health"),
}


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    api_version: str = "3",
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """Call one documented Shlink operation after validating its route."""
    operation = OPERATIONS.get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown Shlink operation: {operation_name}")
    if not api_version.isdigit() or int(api_version) < 1:
        raise ValueError("Shlink API version must be a positive integer.")

    path = operation.path.replace("{version}", api_version)
    values = dict(path_params or {})
    required = _path_parameter_names(path)
    if set(values) != required:
        raise ValueError(
            f"{operation_name} requires path_params {sorted(required)}, got {sorted(values)}."
        )
    for name, value in values.items():
        path = path.replace(f"{{{name}}}", quote(value, safe=""))
    return await client.request(operation.method, path, params=query, json=body)


class ShlinkOperationProvider(Provider):
    """Expose one MCP tool per documented Shlink management operation."""

    def __init__(
        self, client_factory: ServiceClientFactory, api_version: str = "3", auth: Any = None
    ) -> None:
        super().__init__()
        self._tools = tuple(
            _make_operation_tool(name, operation, client_factory, api_version, auth)
            for name, operation in sorted(OPERATIONS.items())
        )

    async def _list_tools(self) -> Sequence[Tool]:
        return self._tools


def _make_operation_tool(
    operation_name: str,
    operation: ShlinkOperation,
    client_factory: ServiceClientFactory,
    api_version: str,
    auth: Any,
) -> Tool:
    async def execute(
        path_params: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        return await call_operation(
            client_factory(),
            operation_name,
            api_version=api_version,
            path_params=path_params,
            query=query,
            body=body,
        )

    tool_name = f"shlink_{operation_name}"
    execute.__name__ = tool_name
    path = operation.path.replace("{version}", api_version)
    return Tool.from_function(
        execute,
        name=tool_name,
        description=f"Shlink {operation.method} {path}. Use JSON request data.",
        annotations=api_operation_annotations(operation.method),
        auth=auth,
    )


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
