"""Dynamic access to supported operations in FreeITSM's OpenAPI document."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from .clients import ServiceClient, ServiceClientFactory
from .tool_annotations import api_operation_annotations

_ALLOWED_METHODS = {"get", "post", "patch", "delete"}
_OPERATIONS_CACHE: dict[str, dict[str, "FreeITSMOperation"]] = {}


@dataclass(frozen=True)
class FreeITSMOperation:
    method: str
    path: str
    encoding: str


def parse_operations(
    specification: Mapping[str, Any], api_path: str = "/api/v1"
) -> dict[str, FreeITSMOperation]:
    """Parse FreeITSM's OpenAPI 3 document into callable JSON operations."""
    paths = specification.get("paths")
    if not isinstance(paths, Mapping):
        raise ValueError("FreeITSM OpenAPI document does not contain paths.")

    prefix = "/" + api_path.strip("/") if api_path.strip("/") else ""
    operations: dict[str, FreeITSMOperation] = {}
    for route, methods in paths.items():
        if not isinstance(route, str) or not isinstance(methods, Mapping):
            continue
        for method, details in methods.items():
            if method not in _ALLOWED_METHODS or not isinstance(details, Mapping):
                continue
            operation_id = details.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            if operation_id in operations:
                raise ValueError(f"Duplicate FreeITSM OpenAPI operation ID: {operation_id}")
            encoding = _request_encoding(details)
            if encoding == "unsupported":
                continue
            operations[operation_id] = FreeITSMOperation(
                method.upper(), f"{prefix}/{route.lstrip('/')}", encoding
            )
    if not operations:
        raise ValueError("FreeITSM OpenAPI document contains no supported operations.")
    return operations


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    operations: Mapping[str, FreeITSMOperation],
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """Call a documented FreeITSM operation after validating its route."""
    operation = operations.get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown FreeITSM operation: {operation_name}")
    if operation.encoding != "json" and body is not None:
        raise ValueError(f"{operation_name} does not accept a JSON body.")

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


class FreeITSMOperationProvider(Provider):
    """Expose one MCP tool per supported FreeITSM REST operation."""

    def __init__(
        self, client_factory: ServiceClientFactory, api_path: str = "/api/v1", auth: Any = None
    ) -> None:
        super().__init__()
        self._client_factory = client_factory
        self._api_path = api_path
        self._auth = auth
        self._tools: dict[str, tuple[Tool, ...]] = {}

    async def _list_tools(self) -> Sequence[Tool]:
        client = self._client_factory()
        operations = await _get_operations(client, self._api_path)
        cache_key = f"{client.base_url}|{self._api_path}"
        if cache_key not in self._tools:
            self._tools[cache_key] = tuple(
                _make_operation_tool(name, operation, operations, self._client_factory, self._auth)
                for name, operation in sorted(operations.items())
            )
        return self._tools[cache_key]


def _make_operation_tool(
    operation_name: str,
    operation: FreeITSMOperation,
    operations: Mapping[str, FreeITSMOperation],
    client_factory: ServiceClientFactory,
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
            operations=operations,
            path_params=path_params,
            query=query,
            body=body,
        )

    suffix = re.sub(r"[^a-z0-9_]+", "_", operation_name.lower()).strip("_")
    tool_name = f"freeitsm_{suffix}"
    execute.__name__ = tool_name
    return Tool.from_function(
        execute,
        name=tool_name,
        description=f"FreeITSM {operation.method} {operation.path}.",
        annotations=api_operation_annotations(operation.method),
        auth=auth,
    )


async def _get_operations(client: ServiceClient, api_path: str) -> dict[str, FreeITSMOperation]:
    if not client.base_url:
        client._url("/")
    cache_key = f"{client.base_url}|{api_path}"
    if cache_key not in _OPERATIONS_CACHE:
        specification = await client.request("GET", f"{api_path.rstrip('/')}/openapi.json")
        if not isinstance(specification, Mapping):
            raise ValueError("FreeITSM OpenAPI endpoint did not return a JSON object.")
        _OPERATIONS_CACHE[cache_key] = parse_operations(specification, api_path)
    return _OPERATIONS_CACHE[cache_key]


def _request_encoding(details: Mapping[str, Any]) -> str:
    request_body = details.get("requestBody")
    if not isinstance(request_body, Mapping):
        return "none"
    content = request_body.get("content")
    if not isinstance(content, Mapping) or not content:
        return "none"
    if "application/json" in content:
        return "json"
    # FreeITSM currently publishes JSON-only bodies. Do not guess how to encode
    # future multipart, form, or binary operations.
    return "unsupported"


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
