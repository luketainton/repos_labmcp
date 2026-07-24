"""MCP tools for Action1's documented REST API."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from .clients import ServiceClient, ServiceClientFactory


@dataclass(frozen=True)
class Action1Operation:
    method: str
    path: str


# Action1's OpenAPI document is published in its interactive documentation.
# Keep the catalogue explicit: it provides stable MCP names while covering the
# operational API areas (endpoints, patching, reports, automations and scripts).
OPERATIONS: dict[str, Action1Operation] = {
    "search": Action1Operation("GET", "/search/{orgId}"),
    "endpoint_status": Action1Operation("GET", "/endpoints/status/{orgId}"),
    "list_endpoints": Action1Operation("GET", "/endpoints/managed/{orgId}"),
    "get_endpoint": Action1Operation("GET", "/endpoints/managed/{orgId}/{endpointId}"),
    "update_endpoint": Action1Operation("PATCH", "/endpoints/managed/{orgId}/{endpointId}"),
    "delete_endpoint": Action1Operation("DELETE", "/endpoints/managed/{orgId}/{endpointId}"),
    "move_endpoint": Action1Operation("POST", "/endpoints/managed/{orgId}/{endpointId}/move"),
    "endpoint_missing_updates": Action1Operation("GET", "/endpoints/managed/{orgId}/{endpointId}/missing-updates"),
    "list_endpoint_groups": Action1Operation("GET", "/endpoints/groups/{orgId}"),
    "create_endpoint_group": Action1Operation("POST", "/endpoints/groups/{orgId}"),
    "get_endpoint_group": Action1Operation("GET", "/endpoints/groups/{orgId}/{groupId}"),
    "update_endpoint_group": Action1Operation("PATCH", "/endpoints/groups/{orgId}/{groupId}"),
    "delete_endpoint_group": Action1Operation("DELETE", "/endpoints/groups/{orgId}/{groupId}"),
    "list_endpoint_group_contents": Action1Operation("GET", "/endpoints/groups/{orgId}/{groupId}/contents"),
    "update_endpoint_group_contents": Action1Operation("POST", "/endpoints/groups/{orgId}/{groupId}/contents"),
    "list_reports": Action1Operation("GET", "/reports/all"),
    "get_report": Action1Operation("GET", "/reports/all/{reportOrCategoryId}"),
    "get_report_data": Action1Operation("GET", "/reportdata/{orgId}/{reportId}/data"),
    "list_vulnerabilities": Action1Operation("GET", "/vulnerabilities/{orgId}"),
    "list_automation_schedules": Action1Operation("GET", "/automations/schedules/{orgId}"),
    "get_automation_schedule": Action1Operation("GET", "/automations/schedules/{orgId}/{automationId}"),
    "apply_automation": Action1Operation("POST", "/automations/instances/{orgId}"),
    "list_scripts": Action1Operation("GET", "/scripts/all"),
    "get_script": Action1Operation("GET", "/scripts/all/{scriptId}"),
    "list_updates": Action1Operation("GET", "/updates/{orgId}"),
    "list_installed_software": Action1Operation("GET", "/installed-software/{orgId}/data"),
}


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    operations: Mapping[str, Action1Operation] = OPERATIONS,
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """Invoke one Action1 operation with safely encoded path parameters."""
    operation = operations.get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown Action1 operation: {operation_name}")
    values = dict(path_params or {})
    required = _path_parameter_names(operation.path)
    if set(values) != required:
        raise ValueError(
            f"{operation_name} requires path_params {sorted(required)}, got {sorted(values)}."
        )
    path = operation.path
    for name, value in values.items():
        path = path.replace(f"{{{name}}}", quote(value, safe=""))
    return await client.request(operation.method, path, params=query, json=body)


class Action1OperationProvider(Provider):
    """Expose individually discoverable MCP tools for Action1 operations."""

    def __init__(self, client_factory: ServiceClientFactory, auth: Any = None) -> None:
        super().__init__()
        self._client_factory = client_factory
        self._auth = auth
        self._tools: tuple[Tool, ...] | None = None

    async def _list_tools(self) -> Sequence[Tool]:
        if self._tools is None:
            self._tools = tuple(
                _make_operation_tool(name, operation, self._client_factory, self._auth)
                for name, operation in sorted(OPERATIONS.items())
            )
        return self._tools


def _make_operation_tool(
    operation_name: str,
    operation: Action1Operation,
    client_factory: ServiceClientFactory,
    auth: Any,
) -> Tool:
    async def execute(
        path_params: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        return await call_operation(
            client_factory(), operation_name, path_params=path_params, query=query, body=body
        )

    tool_name = f"action1_{re.sub(r'[^a-z0-9_]+', '_', operation_name).strip('_')}"
    execute.__name__ = tool_name
    return Tool.from_function(
        execute,
        name=tool_name,
        description=f"Action1 {operation.method} {operation.path}.",
        auth=auth,
    )


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
