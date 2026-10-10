# Proposal

## Why

LabMCP currently connects to several home-lab services but does not expose FreeITSM through MCP. Adding a FreeITSM integration will let users access its supported IT service management API alongside the existing integrations.

## What Changes

- Add a FreeITSM service integration with individually discoverable MCP tools for supported API operations.
- Configure the FreeITSM API endpoint and authentication through server-side settings, following the API's documented security scheme.
- Add FreeITSM to the service-specific MCP endpoint catalogue and document its configuration and tools.
- Exclude operations that cannot be represented safely through the existing MCP tool interface, such as binary transfers, unless FreeITSM's API exposes an appropriate JSON alternative.

## Capabilities

### New Capabilities
- `freeitsm-integration`: Configure FreeITSM access and expose its supported API operations as MCP tools.

### Modified Capabilities

## Impact

- Likely code areas: `src/labmcp/clients.py`, `src/labmcp/config.py`, `src/labmcp/server.py`, and a new FreeITSM API provider module.
- User documentation: `README.md` and `docs/services.md`.
- External dependency: the FreeITSM API described by `https://itsm.tainton.uk/api/v1/openapi.json`.
- The OpenAPI URL could not be resolved from the current environment during proposal authoring. Implementation must inspect the live schema to confirm its base URL, authentication scheme, operation coverage, and any unsupported payload types before finalizing the operation catalogue.
