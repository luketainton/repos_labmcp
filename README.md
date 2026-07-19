# labmcp

Unified [Model Context Protocol](https://modelcontextprotocol.io/) server for a home lab. It currently exposes Gitea and Pocket ID through one FastMCP process.

## Exposed tools

Gitea:

- `gitea_list_repositories`
- `gitea_get_repository`
- `gitea_list_issues`
- `gitea_create_issue`

Pocket ID:

- `pocket_id_openid_configuration`
- `pocket_id_health`
- `pocket_id_get_json` for documented Pocket ID API endpoints
- `labmcp_get_version`

Pocket ID API requests use the documented `X-API-KEY` header. OIDC discovery and health checks do not require a key. The generic JSON tool intentionally supports GET only, so mutating identity-management operations cannot be triggered accidentally.

## Local development

Install [uv](https://docs.astral.sh/uv/), copy `.env.example` to `.env`, and set the service URLs and credentials:

```sh
cp .env.example .env
uv sync --dev
uv run labmcp
```

The default transport is stdio, which works with MCP clients that launch local servers. For a network endpoint, set `MCP_TRANSPORT=http`, then configure `MCP_HOST` and `MCP_PORT`.

Gitea tokens and Pocket ID API keys should be supplied through secrets or environment variables, never committed to the repository. Pocket ID's API key can be created under `/settings/admin/api-keys`.

## MCP client authentication

The server allows unauthenticated stdio because the MCP client starts a local process. Network transports are different: `MCP_TRANSPORT=http`, `sse`, or `streamable-http` require `MCP_AUTH_MODE=jwt` or `oidc_proxy`.

Use `oidc_proxy` when clients should start an interactive login flow and send you to Pocket ID on first connect. Create an OIDC client in Pocket ID for this MCP server, add the callback URL `https://labmcp.example.com/auth/callback`, then configure:

```sh
MCP_TRANSPORT=sse
MCP_AUTH_MODE=oidc_proxy
MCP_AUTH_BASE_URL=https://labmcp.example.com
MCP_AUTH_OIDC_CLIENT_ID=<pocket-id-client-id>
MCP_AUTH_OIDC_CLIENT_SECRET=<pocket-id-client-secret>
MCP_AUTH_OIDC_JWT_SIGNING_KEY=<stable-random-secret>
MCP_AUTH_REQUIRED_SCOPES=openid,profile
```

By default, `MCP_AUTH_OIDC_CONFIG_URL` is derived as `<POCKET_ID_URL>/.well-known/openid-configuration`, and the callback path is `/auth/callback`. Set them explicitly if your Pocket ID issuer or reverse proxy path differs from `POCKET_ID_URL`.

After login, MCP clients authenticate with bearer tokens:

```http
Authorization: Bearer <mcp-issued-token>
```

Use `jwt` mode only when clients already have a Pocket ID JWT and should skip the interactive login handoff:

```sh
MCP_AUTH_MODE=jwt
MCP_AUTH_JWT_AUDIENCE=<pocket-id-client-id>
```

In `jwt` mode, `MCP_AUTH_JWT_ISSUER` defaults to `POCKET_ID_URL`, and `MCP_AUTH_JWT_JWKS_URI` defaults to `<issuer>/.well-known/jwks.json`. If you configure `MCP_AUTH_REQUIRED_SCOPES`, provide a comma-separated list of scopes that must be present in the token.

## CI and code quality

Pull requests run `.gitea/workflows/ci.yml`, which installs dependencies with `uv`, runs Ruff, executes tests through Coverage.py, writes `testresults.xml` and `coverage.xml`, prints the coverage summary, compiles the Python sources, and builds a Docker image.

`.gitea/workflows/sonar.yml` runs the same Ruff, test, and Coverage.py commands as CI, then normalizes the coverage paths and submits the reports to SonarQube. Configure `SONAR_URL` as a repository variable and `SONAR_TOKEN` as a repository secret.

## Docker

```sh
docker build -t labmcp:local .
docker run --rm -i \
  -e GITEA_URL -e GITEA_TOKEN \
  -e POCKET_ID_URL -e POCKET_ID_TOKEN \
  labmcp:local
```

For HTTP transport, also pass `-e MCP_TRANSPORT=http -p 8000:8000`.

## Releases

Pushing a tag such as `v0.1.0` starts `.gitea/workflows/release.yml`. The workflow builds and pushes both `${PACKAGES_REGISTRY_URL}/owner/labmcp:v0.1.0` and `:latest`; configure `PACKAGES_REGISTRY_URL` and `ACTIONS_USERNAME` as variables plus `ACTIONS_TOKEN` as a secret.

The release job runs `uv version` against the checked-out source using the tag without its `v` prefix, then builds the image. At runtime, `labmcp_get_version` reads that installed package metadata, so the package version does not need to be duplicated in Python code.
