"""Validated access to the configured Gitea instance's published Swagger API."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .clients import ServiceClient

_ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}
_OPERATIONS_CACHE: dict[str, dict[str, "GiteaOperation"]] = {}


@dataclass(frozen=True)
class GiteaOperation:
    method: str
    path: str
    encoding: str


def parse_operations(specification: Mapping[str, Any]) -> dict[str, GiteaOperation]:
    """Build a safe operation registry from Gitea's Swagger v1 document."""
    paths = specification.get("paths")
    if not isinstance(paths, Mapping):
        raise ValueError("Gitea Swagger document does not contain paths.")

    operations: dict[str, GiteaOperation] = {}
    for path, methods in paths.items():
        if not isinstance(path, str) or not isinstance(methods, Mapping):
            continue
        for method, details in methods.items():
            if method not in _ALLOWED_METHODS or not isinstance(details, Mapping):
                continue
            operation_id = details.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                continue
            parameters = details.get("parameters", [])
            if (
                not isinstance(parameters, list)
                or _has_binary_parameter(parameters)
                or _has_binary_response(details)
            ):
                continue
            encoding = "form" if _has_form_parameter(parameters) else "json"
            if operation_id in operations:
                raise ValueError(f"Duplicate Gitea Swagger operation ID: {operation_id}")
            operations[operation_id] = GiteaOperation(method.upper(), f"/api/v1{path}", encoding)
    if not operations:
        raise ValueError("Gitea Swagger document contains no supported operations.")
    return operations


async def list_operations(client: ServiceClient, *, refresh: bool = False) -> list[dict[str, str]]:
    """Return all supported operations from the configured Gitea instance."""
    operations = await _get_operations(client, refresh=refresh)
    return [
        {
            "operation": name,
            "method": operation.method,
            "path": operation.path,
            "encoding": operation.encoding,
        }
        for name, operation in sorted(operations.items())
    ]


async def call_operation(
    client: ServiceClient,
    operation_name: str,
    *,
    path_params: Mapping[str, str] | None = None,
    query: Mapping[str, Any] | None = None,
    body: Any = None,
    form: Mapping[str, Any] | None = None,
) -> Any:
    """Call one Gitea operation after validating it against the Swagger document."""
    operation = (await _get_operations(client)).get(operation_name)
    if operation is None:
        raise ValueError(f"Unknown Gitea operation: {operation_name}")
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


async def _get_operations(
    client: ServiceClient,
    *,
    refresh: bool = False,
) -> dict[str, GiteaOperation]:
    if not client.base_url:
        client._url("/")
    cache_key = client.base_url or ""
    if refresh or cache_key not in _OPERATIONS_CACHE:
        specification = await client.request("GET", "/swagger.v1.json")
        if not isinstance(specification, Mapping):
            raise ValueError("Gitea Swagger endpoint did not return a JSON object.")
        _OPERATIONS_CACHE[cache_key] = parse_operations(specification)
    return _OPERATIONS_CACHE[cache_key]


def _has_binary_parameter(parameters: list[Any]) -> bool:
    return any(
        isinstance(parameter, Mapping)
        and parameter.get("in") == "formData"
        and parameter.get("type") == "file"
        for parameter in parameters
    )


def _has_form_parameter(parameters: list[Any]) -> bool:
    return any(
        isinstance(parameter, Mapping) and parameter.get("in") == "formData"
        for parameter in parameters
    )


def _has_binary_response(details: Mapping[str, Any]) -> bool:
    produces = details.get("produces", [])
    if isinstance(produces, list) and any(
        isinstance(content_type, str) and not content_type.endswith("json")
        for content_type in produces
    ):
        return True
    responses = details.get("responses", {})
    return isinstance(responses, Mapping) and any(
        isinstance(response, Mapping)
        and isinstance(response.get("schema"), Mapping)
        and response["schema"].get("type") == "file"
        for response in responses.values()
    )


def _path_parameter_names(path: str) -> set[str]:
    return {segment[1:-1] for segment in path.split("/") if segment.startswith("{")}
