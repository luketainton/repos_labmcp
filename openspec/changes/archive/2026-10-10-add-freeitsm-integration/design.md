# Design

## Context

LabMCP has service-specific MCP endpoints registered in `src/labmcp/server.py`. Meraki and Pangolin providers build individually named tools from OpenAPI documents; `Settings` holds service URLs and secrets, while shared `ServiceClient` handles requests and HTTP errors. See `proposal.md` for motivation and `specs/freeitsm-integration/spec.md` for observable requirements.

The supplied schema is OpenAPI 3.0.3 for FreeITSM REST API 1.0.0. It declares a relative `/api/v1` server and HTTP bearer auth (`Authorization: Bearer fitsm_...`). The document contains 246 unique operation IDs: 130 GET, 53 POST, 28 PATCH, and 35 DELETE operations. All request bodies use JSON; responses use JSON; there are no multipart, form, or binary payloads. Operations span tickets, assets, problems, changes, knowledge, tasks, CMDB, contracts, suppliers, domains, cost centres, projects, calendar, software, service status/incidents, morning checks, forms, workflows, network diagrams, users, analysts, and reference data.

## Goals / Non-Goals

**Goals:**

- Integrate FreeITSM using LabMCP's established service and OpenAPI-provider conventions.
- Keep credentials in server configuration and use the scheme defined by FreeITSM.
- Support the documented operations that map cleanly to JSON-oriented MCP tool inputs and outputs.

**Non-Goals:**

- Invent or hard-code an authentication mechanism before inspecting the FreeITSM schema and deployment documentation.
- Expose binary upload/download operations without an MCP-compatible representation.
- Add FreeITSM-specific authorization semantics beyond the existing per-service access controls.

## Decisions

- **Use a dedicated FreeITSM OpenAPI provider.** Follow the Meraki/Pangolin pattern for loading an OpenAPI document, producing stable `freeitsm_*` operation tools, validating path parameters, and filtering unsupported payload types. This keeps the integration discoverable and consistent with other API-backed services. A hand-maintained list would drift from the API; a generic arbitrary-URL tool would weaken operation-specific tool descriptions and validation.
- **Use service-specific configuration and registration.** Add FreeITSM settings and a client factory, register its provider and endpoint under the `freeitsm` service key, and document its environment variables and endpoint. Follow current `SERVICE_PATHS` and service authorization integration points.
- **Configure `FREEITSM_URL`, `FREEITSM_API_PATH` (default `/api/v1`), and `FREEITSM_API_KEY` from the verified schema.** The configured URL is the origin; the provider fetches `<URL><API_PATH>/openapi.json` and prefixes documented operation routes with the API path. The API key uses the standard bearer scheme. Operation IDs are unique and normalize to unique tool suffixes, so names can remain stable as `freeitsm_<operationId>`.
- **Retain request parameter conventions.** Exposed operations should use the established `path_params`, `query`, `body`, and where supported `form` inputs, with secrets injected server-side. Keep stable operation names and safe URL encoding as used by existing providers.

## Risks / Trade-offs

- [OpenAPI document or API host becomes unreachable at runtime] → Return the shared service request error and document the configured URL/API path; do not fall back to guessed routes or unauthenticated calls.
- [FreeITSM OpenAPI constructs may exceed the existing provider's input model] → Identify unsupported constructs during schema inspection and either map them explicitly or exclude them with documented rationale.
- [Large operation catalogues can make tool discovery noisy] → Preserve individual operation tools on the dedicated endpoint and consider filtering only operations proven unsafe or incompatible with the current MCP interface.

## Migration Plan

1. Add optional FreeITSM configuration; existing deployments remain usable when it is unset.
2. Deploy the updated LabMCP and configure the FreeITSM API URL and documented credential through the environment or secret store.
3. Connect clients to the FreeITSM service endpoint and verify tool discovery and a read-only operation.
4. Roll back by reverting the deployment and removing the FreeITSM settings; no persisted data migration is expected.
