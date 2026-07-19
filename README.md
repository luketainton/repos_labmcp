# labmcp

Unified [Model Context Protocol](https://modelcontextprotocol.io/) server for a home lab. It currently exposes Gitea, Pocket ID, and n8n through one FastMCP process.

## Exposed tools

Gitea:

- `gitea_list_repositories`
- `gitea_get_repository`
- `gitea_list_issues`
- `gitea_create_issue`
- one individually discoverable `gitea_*` tool for every supported Gitea Swagger operation

Pocket ID:

- `pocket_id_openid_configuration`
- `pocket_id_health`
- one individually discoverable `pocket_id_*` tool for every supported Pocket ID operation
- `labmcp_get_version`

n8n:

- one individually discoverable `n8n_*` tool for every supported operation in n8n's OpenAPI document

Pocket ID API requests use the documented `X-API-KEY` header. OIDC discovery and health checks do not require a key. Each supported JSON/form endpoint is exposed as its own tool, including user, group, OIDC client, API key, custom claim, SCIM, and administrative operations. Binary image upload/download endpoints are excluded because they need an MCP attachment interface.

Gitea's tools are generated from `<GITEA_URL>/swagger.v1.json` and cached when the server first serves tool discovery. This exposes the documented non-binary operations for the running Gitea version as individual `gitea_*` tools. Restart labmcp after a Gitea upgrade to rebuild the catalogue. The Gitea token is supplied using Gitea's `Authorization: token ...` scheme.

n8n's tools are generated from `<N8N_URL><N8N_API_PATH>/openapi.yml` (default path: `/api/v1`) and cached when the server first serves tool discovery. The n8n API key is supplied using the `X-N8N-API-KEY` header. Operations accept `path_params`, `query`, and either `body` or `form` arguments.

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
MCP_AUTH_REQUIRED_SCOPES=openid,profile,groups
```

By default, `MCP_AUTH_OIDC_CONFIG_URL` is derived as `<POCKET_ID_URL>/.well-known/openid-configuration`, and the callback path is `/auth/callback`. Set them explicitly if your Pocket ID issuer or reverse proxy path differs from `POCKET_ID_URL`.

Pocket ID rejects the OAuth `resource` indicator used by some MCP clients. The server therefore defaults `MCP_AUTH_OIDC_FORWARD_RESOURCE=false`; leave it unchanged for Pocket ID.

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

### Service access by Pocket ID group or role

Tools can be made visible only to users in specific Pocket ID groups. Request Pocket ID's `groups` scope and map each service to one or more permitted groups:

```sh
MCP_AUTH_REQUIRED_SCOPES=openid,profile,groups
MCP_AUTH_GROUP_CLAIM=groups
MCP_SERVICE_GROUPS={"gitea":["mcp-gitea"],"pocket_id":["mcp-pocket-id"]}
```

Membership of any group listed for a service permits access to that service's tools. The Gitea tools use the `gitea` service key; all Pocket ID tools use `pocket_id`. Once `MCP_SERVICE_GROUPS` is non-empty, any omitted service is denied. Leave it as `{}` only when every authenticated user should have access to all services.

Pocket ID normally provides groups in the `groups` claim. To authorize from a custom role claim instead, configure that custom claim on the relevant Pocket ID groups, set `MCP_AUTH_GROUP_CLAIM` to its name, and use its values in `MCP_SERVICE_GROUPS`.

## CI and code quality

Pull requests run `.gitea/workflows/ci.yml`, which installs dependencies with `uv`, runs Ruff, executes tests through Coverage.py, writes `testresults.xml` and `coverage.xml`, prints the coverage summary, compiles the Python sources, and builds a Docker image.

`.gitea/workflows/sonar.yml` runs the same Ruff, test, and Coverage.py commands as CI, then submits the reports to SonarQube. Configure `SONAR_URL` as a repository variable and `SONAR_TOKEN` as a repository secret.

## Docker

```sh
docker build -t labmcp:local .
docker run --rm -i \
  -e GITEA_URL -e GITEA_TOKEN \
  -e POCKET_ID_URL -e POCKET_ID_TOKEN \
  -e N8N_URL -e N8N_API_KEY \
  labmcp:local
```

For HTTP transport, also pass `-e MCP_TRANSPORT=http -p 8000:8000`.

When using `MCP_AUTH_MODE=oidc_proxy`, mount a persistent volume at
`/home/labmcp/.local/share`. FastMCP stores OAuth client-registration state there;
without it, clients may need to register again after the container is recreated.

## Releases

Pushing a tag such as `v0.1.0` starts `.gitea/workflows/release.yml`. The workflow builds and pushes both `${PACKAGES_REGISTRY_URL}/owner/labmcp:v0.1.0` and `:latest`; configure `PACKAGES_REGISTRY_URL` and `ACTIONS_USERNAME` as variables plus `ACTIONS_TOKEN` as a secret.

The release job runs `uv version` against the checked-out source using the tag without its `v` prefix, then builds the image. At runtime, `labmcp_get_version` reads that installed package metadata, so the package version does not need to be duplicated in Python code.
