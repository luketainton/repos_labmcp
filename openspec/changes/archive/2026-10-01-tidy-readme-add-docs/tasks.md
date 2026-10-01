# Tasks

## 1. Organize the documentation

- [x] 1.1 Move the service catalogue and service-specific configuration from README.md into docs/services.md; verify all existing service guidance is retained and README links to the guide.
- [x] 1.2 Move MCP authentication guidance into docs/authentication.md; verify both JWT and OIDC proxy instructions and service access mappings remain present and linked from README.md.
- [x] 1.3 Move development, CI, Docker, and release instructions into docs/development-and-deployment.md; verify all sections remain present and linked from README.md.
- [x] 1.4 Rewrite README.md as an overview, quick start, and documentation index; verify every relative documentation link resolves.

## 2. Skip CI for documentation-only changes

- [x] 2.1 Add Markdown and docs/** path-ignore filters to pull_request and main/master push triggers in .gitea/workflows/ci.yml; verify workflow parsing and confirm workflow_dispatch remains enabled.
- [x] 2.2 Verify the trigger patterns exclude docs-only changes and still include mixed documentation and code changes using the workflow platform's supported path-filter semantics.

## 3. Integration verification

- [x] 3.1 Review the final diff to confirm all original README guidance is preserved and only documentation and CI trigger behavior changed.
