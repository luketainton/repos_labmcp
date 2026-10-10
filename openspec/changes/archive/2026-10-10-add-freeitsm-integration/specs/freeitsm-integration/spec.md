# Spec Delta

## Purpose

This capability connects LabMCP clients to FreeITSM through a configurable, authenticated MCP integration that exposes the supported FreeITSM API operations.

## ADDED Requirements

### Requirement: Configure FreeITSM API access
LabMCP SHALL allow an operator to configure the FreeITSM API base URL and any required API credential using server-side configuration.

#### Scenario: FreeITSM is configured
- **WHEN** valid FreeITSM connection settings are supplied
- **THEN** FreeITSM MCP operations use that API endpoint and documented authentication scheme

#### Scenario: FreeITSM is not configured
- **WHEN** a client invokes a FreeITSM operation without a configured API base URL
- **THEN** LabMCP returns a clear configuration error identifying the required setting

### Requirement: Expose supported FreeITSM operations
LabMCP SHALL expose individually discoverable MCP tools for the supported non-binary operations documented by the configured FreeITSM OpenAPI specification.

#### Scenario: Discover FreeITSM operations
- **WHEN** a client lists tools on the FreeITSM-specific MCP endpoint
- **THEN** it receives FreeITSM operation tools with stable FreeITSM-prefixed names and descriptions of their API operation

#### Scenario: Invoke an operation with parameters
- **WHEN** a client invokes a FreeITSM operation with valid path, query, and request-body inputs
- **THEN** LabMCP sends the corresponding HTTP request to FreeITSM and returns the API response

#### Scenario: Reject invalid operation parameters
- **WHEN** a client invokes an operation with missing or mismatched path parameters or incompatible request encodings
- **THEN** LabMCP returns a clear validation error without sending the request

### Requirement: Preserve FreeITSM credential confidentiality
LabMCP SHALL keep FreeITSM credentials server-side and SHALL NOT expose them as MCP tool arguments or include them in tool results or logs.

#### Scenario: Authenticated API request
- **WHEN** LabMCP sends a FreeITSM request that requires authentication
- **THEN** it supplies the configured credential using the authentication scheme documented by FreeITSM

#### Scenario: Tool discovery and logging
- **WHEN** a client lists or invokes FreeITSM tools
- **THEN** credentials are absent from tool schemas, returned data added by LabMCP, and LabMCP tool-call logs

### Requirement: Provide a dedicated FreeITSM MCP endpoint
LabMCP SHALL provide a service-specific MCP endpoint whose tool catalogue contains FreeITSM tools and does not include tools from unrelated integrations.

#### Scenario: Connect to FreeITSM endpoint
- **WHEN** a client connects to the FreeITSM service endpoint
- **THEN** it can discover and invoke FreeITSM tools independently of the aggregate MCP catalogue
