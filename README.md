# labmcp

Unified [Model Context Protocol](https://modelcontextprotocol.io/) server for a home lab, bringing Gitea, Pocket ID, n8n, Meraki, Pangolin, Shlink, Pushover, and Action1 tools together in one FastMCP process.

## Quick start

Install [uv](https://docs.astral.sh/uv/), configure the service URLs and credentials, then run LabMCP locally:

```sh
cp .env.example .env
uv sync --dev
uv run labmcp
```

The default transport is stdio. For a network endpoint, set `MCP_TRANSPORT=http`, then configure `MCP_HOST` and `MCP_PORT`. Network transports require authentication; see the [authentication guide](docs/authentication.md).

## Documentation

- [Services and tools](docs/services.md): available tools, service endpoints, and credentials.
- [MCP client authentication](docs/authentication.md): JWT, OIDC proxy, and service access configuration.
- [Development and deployment](docs/development-and-deployment.md): local development, CI, Docker, and releases.

Keep tokens, API keys, and other credentials in environment variables or a secret store. Never commit them to the repository.
