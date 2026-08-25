"""MCP tool-behavior annotations shared by service providers."""

from mcp.types import ToolAnnotations


def api_operation_annotations(method: str) -> ToolAnnotations:
    """Describe an HTTP API operation conservatively for MCP clients.

    API calls cross the MCP server's trust boundary, so they are open-world.
    Only GET is read-only. DELETE is destructive but repeat-safe; PUT is
    repeat-safe by HTTP semantics. Other mutation methods retain the protocol's
    conservative defaults for destructiveness and idempotency.
    """
    method = method.upper()
    if method == "GET":
        return ToolAnnotations(readOnlyHint=True, openWorldHint=True)
    if method == "DELETE":
        return ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        )
    if method == "PUT":
        return ToolAnnotations(readOnlyHint=False, idempotentHint=True, openWorldHint=True)
    return ToolAnnotations(readOnlyHint=False, openWorldHint=True)
