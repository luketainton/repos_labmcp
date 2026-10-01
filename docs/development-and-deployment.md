# Development and deployment

## Local development

Install [uv](https://docs.astral.sh/uv/), copy `.env.example` to `.env`, and set the service URLs and credentials:

```sh
cp .env.example .env
uv sync --dev
uv run labmcp
```

The default transport is stdio, which works with MCP clients that launch local servers. For a network endpoint, set `MCP_TRANSPORT=http`, then configure `MCP_HOST` and `MCP_PORT`. One network process exposes the legacy full catalogue at `/mcp` and smaller per-application catalogues at `/gitea`, `/pocketid`, `/n8n`, `/meraki`, `/pangolin`, `/shlink`, `/action1`, and `/pushover`. Connect ChatGPT or Codex to the application path you need.

Gitea tokens and Pocket ID API keys should be supplied through secrets or environment variables, never committed to the repository. Pocket ID's API key can be created under `/settings/admin/api-keys`.

## CI and code quality

Pull requests with code or other non-documentation changes run `.gitea/workflows/ci.yml`, which calls the shared `ci-python-unified.yml` workflow. Pull requests and pushes to `main` or `master` that change only Markdown files or files under `docs/` are skipped; manual workflow dispatch remains available. It installs dependencies with `uv`, runs Ruff and tests through Coverage.py, writes `testresults.xml` and `coverage.xml`, prints the coverage summary, compiles the Python sources, builds a Docker image, and enables SonarQube and security scanning. Configure `SONAR_TOKEN` as a repository secret.

## Docker

```sh
docker build -t labmcp:local .
docker run --rm -i \
  -e GITEA_URL -e GITEA_TOKEN \
  -e POCKET_ID_URL -e POCKET_ID_TOKEN \
  -e N8N_URL -e N8N_API_KEY \
  -e MERAKI_URL -e MERAKI_DASHBOARD_API_KEY \
  -e PANGOLIN_URL -e PANGOLIN_API_KEY \
  -e SHLINK_URL -e SHLINK_API_KEY \
  -e PUSHOVER_APP_TOKEN -e PUSHOVER_USER_KEY \
  -e ACTION1_URL -e ACTION1_CLIENT_ID -e ACTION1_CLIENT_SECRET \
  labmcp:local
```

For HTTP transport, also pass `-e MCP_TRANSPORT=http -p 8000:8000`.

When using `MCP_AUTH_MODE=oidc_proxy`, mount a persistent volume at
`/home/labmcp/.local/share`. FastMCP stores OAuth client-registration state there;
without it, clients may need to register again after the container is recreated.

## Releases

Pushing a tag such as `v0.1.0` starts `.gitea/workflows/release.yml`. The workflow builds and pushes both `${PACKAGES_REGISTRY_URL}/owner/labmcp:v0.1.0` and `:latest`; configure `PACKAGES_REGISTRY_URL` and `ACTIONS_USERNAME` as variables plus `ACTIONS_TOKEN` as a secret.

The release job runs `uv version` against the checked-out source using the tag without its `v` prefix, then builds the image. At runtime, `labmcp_get_version` reads that installed package metadata, so the package version does not need to be duplicated in Python code.
