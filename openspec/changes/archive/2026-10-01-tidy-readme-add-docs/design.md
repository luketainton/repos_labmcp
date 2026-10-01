# Design

## Context

See proposal.md for motivation and specs/ci-workflow/spec.md for the required CI trigger behavior. The README currently contains the complete service catalogue, setup and authentication guides, development and CI instructions, Docker usage, and release information. CI is configured in `.gitea/workflows/ci.yml`; release publishing is a separate tag-triggered workflow.

## Goals / Non-Goals

**Goals:**
- Make the README a concise entry point with a quick start and links to detailed guides.
- Preserve the current instructions in focused pages under `docs/`.
- Exclude documentation-only PRs and default-branch pushes from CI.

**Non-Goals:**
- Change application behavior, supported services, release publishing, or CI job contents.
- Exclude changes to workflow or other configuration files from CI.

## Decisions

### Keep documentation in three focused guides

Move the service catalogue and service-specific setup into `docs/services.md`, authentication configuration into `docs/authentication.md`, and development, CI, Docker, and release guidance into `docs/development-and-deployment.md`. Keep `README.md` as the project overview, local quick start, and navigation page. This keeps the current material findable without an overly long single guide.

### Filter documentation-only changes at workflow triggers

Add path-ignore filters to both `pull_request` and default-branch `push` triggers in `.gitea/workflows/ci.yml` for Markdown files and `docs/**`. Workflow-level filtering prevents the reusable CI workflow and its dependent checks from starting for those events. Leave `workflow_dispatch` unchanged. Keep release publishing unchanged because it is triggered by version tags, not PRs or branch pushes.

## Risks / Trade-offs

- Path-filter support or glob behavior can differ across Gitea Actions versions. Validate the workflow syntax against the repository's supported runner behavior before relying on it.
- Workflow-level filtering means documentation-only PRs have no CI run; branch protection must not require a CI check to be created for those PRs.
