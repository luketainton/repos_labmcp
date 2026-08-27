"""Dynamic access to every supported operation in Pangolin's OpenAPI document."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote

from fastmcp.server.providers import Provider
from fastmcp.tools import Tool

from .clients import ServiceClient, ServiceClientFactory
from .tool_annotations import api_operation_annotations

_ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}
_OPERATIONS_CACHE: dict[str, dict[str, "PangolinOperation"]] = {}


@dataclass(frozen=True)
class PangolinOperation:
    method: str
    path: str
    encoding: str


def parse_operations(specification: Mapping[str, Any], api_path: str = "/v1") -> dict[str, PangolinOperation]:
    """Parse Pangolin's OpenAPI 3 document into safe, callable operation metadata."""
    paths = specification.get("paths")
    if not isinstance(paths, Mapping):
        raise ValueError("Pangolin OpenAPI document does not contain paths.")

    prefix = "/" + api_path.strip("/") if api_path.strip("/") else ""
    operations: dict[str, PangolinOperation] = {}
    for route, methods in paths.items():
        if not isinstance(route, str) or not isinstance(methods, Mapping):
            continue
        for method, details in methods.items():
            if method not in _ALLOWED_METHODS or not isinstance(details, Mapping):
                continue
            encoding = _request_encoding(details)
            if encoding == "binary":
                continue
            operation_name = f"{method}:{route}"
            if operation_name in operations:
                raise ValueError(f"Duplicate Pangolin OpenAPI operation: {operation_name}")
            operations[operation_name] = PangolinOperation(
                method.upper(), f"{prefix}/{route.lstrip('/')}", encoding
            )
    if not operations:
        raise ValueError("Pangolin OpenAPI document contains no supported operations.")
    return operations


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    operations: Mapping[str, PangolinOperation],
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
    form: Mapping[str, Any] | None = None,
) -> Any:
    """Call one documented Pangolin operation after validating its route."""
    operation = operations.get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown Pangolin operation: {operation_name}")
    if body is not None and form is not None:
        raise ValueError("Provide either body or form, not both.")
    if operation.encoding == "form" and body is not None:
        raise ValueError(f"{operation_name} requires form data, not a JSON body.")
    if operation.encoding == "json" and form is not None:
        raise ValueError(f"{operation_name} requires a JSON body, not form data.")

    values = dict(path_params or {})
    required = _path_parameter_names(operation.path)
    if set(values) != required:
        raise ValueError(
            f"{operation_name} requires path_params {sorted(required)}, got {sorted(values)}."
        )
    path = operation.path
    for name, value in values.items():
        path = path.replace(f"{{{name}}}", quote(value, safe=""))
    return await client.request(operation.method, path, params=query, json=body, data=form)


class PangolinOperationProvider(Provider):
    """Expose one MCP tool for every supported operation in Pangolin's live spec."""

    def __init__(self, client_factory: ServiceClientFactory, api_path: str = "/v1", auth: Any = None) -> None:
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
    operation: PangolinOperation,
    operations: Mapping[str, PangolinOperation],
    client_factory: ServiceClientFactory,
    auth: Any,
) -> Tool:
    async def execute(
        path_params: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
        form: dict[str, Any] | None = None,
    ) -> Any:
        return await call_operation(
            client_factory(),
            operation_name,
            operations=operations,
            path_params=path_params,
            query=query,
            body=body,
            form=form,
        )

    tool_name = _tool_name(operation_name)
    execute.__name__ = tool_name
    description = (
        f"Pangolin {operation.method} {operation.path}. "
        f"Use {'form' if operation.encoding == 'form' else 'JSON'} request data."
    )
    return Tool.from_function(
        execute,
        name=tool_name,
        description=description,
        annotations=api_operation_annotations(operation.method),
        auth=auth,
    )


def _tool_name(operation_name: str) -> str:
    """Create a stable tool name from Pangolin's method and route.

    Pangolin's OpenAPI document does not supply operation IDs, so its route is
    the source of truth. Keeping the API-path prefix out of the name means a
    self-hosted deployment can customize ``PANGOLIN_API_PATH`` without changing
    the MCP tool catalogue.
    """
    method, route = operation_name.split(":", maxsplit=1)
    path = re.sub(r"\{([^}]+)\}", r"by_\1", route)
    path = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").lower()
    return f"pangolin_{method}_{path}"


async def _get_operations(client: ServiceClient, api_path: str) -> dict[str, PangolinOperation]:
    if not client.base_url:
        client._url("/")
    cache_key = f"{client.base_url}|{api_path}"
    if cache_key not in _OPERATIONS_CACHE:
        specification = await client.request("GET", f"{api_path.rstrip('/')}/openapi.json")
        if not isinstance(specification, Mapping):
            raise ValueError("Pangolin OpenAPI endpoint did not return a JSON object.")
        _OPERATIONS_CACHE[cache_key] = parse_operations(specification, api_path)
    return _OPERATIONS_CACHE[cache_key]


def _request_encoding(details: Mapping[str, Any]) -> str:
    request_body = details.get("requestBody")
    if not isinstance(request_body, Mapping):
        return "json"
    content = request_body.get("content")
    if not isinstance(content, Mapping):
        return "json"
    if "application/json" in content or not content:
        return "json"
    if "application/x-www-form-urlencoded" in content:
        return "form"
    if "multipart/form-data" in content:
        return "binary" if _contains_binary(content["multipart/form-data"]) else "form"
    return "json"


def _contains_binary(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_binary(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_binary(item) for item in value)
    return value == "binary"


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
