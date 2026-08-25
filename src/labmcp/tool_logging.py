"""Audit logging for MCP tool invocations."""

import json
from typing import Any

from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.utilities.logging import get_logger


logger = get_logger(__name__)


class ToolCallLoggingMiddleware(Middleware):
    """Log every tool call after it has produced a result or an error."""

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Any]
    ) -> Any:
        user = _user(context)
        tool = context.message.name
        params = context.message.arguments or {}
        redact_contents = tool.startswith("pushover_")
        try:
            result = await call_next(context)
        except Exception as error:
            logged_params = _redacted() if redact_contents else _json(params)
            logged_output = _redacted() if redact_contents else _json({"error": str(error)})
            logger.info(
                'user="%s" tool="%s" params="%s" output="%s"',
                _escape(user),
                _escape(tool),
                _escape(logged_params),
                _escape(logged_output),
            )
            raise

        logged_params = _redacted() if redact_contents else _json(params)
        logged_output = _redacted() if redact_contents else _json(result)
        logger.info(
            'user="%s" tool="%s" params="%s" output="%s"',
            _escape(user),
            _escape(tool),
            _escape(logged_params),
            _escape(logged_output),
        )
        return result


def _user(context: MiddlewareContext[Any]) -> str:
    """Return the most useful stable identity supplied by FastMCP authentication."""
    token = get_access_token()
    if token is not None:
        claims = token.claims
        for claim in ("preferred_username", "email", "sub"):
            value = claims.get(claim)
            if isinstance(value, str) and value:
                return value
        if token.client_id:
            return token.client_id
    if context.fastmcp_context and context.fastmcp_context.client_id:
        return context.fastmcp_context.client_id
    return "anonymous"


def _json(value: Any) -> str:
    """Serialize arbitrary MCP inputs and outputs without breaking the audit log."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, default=str, separators=(",", ":"), sort_keys=True)


def _redacted() -> str:
    """Return the fixed audit placeholder for confidential tool content."""
    return '{"redacted":true}'


def _escape(value: str) -> str:
    """Make a value safe for a single key=\"value\" log field."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
