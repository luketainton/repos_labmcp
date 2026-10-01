# Proposal

## Why

The README combines a project overview with lengthy service, authentication, development, and deployment instructions, making common information harder to find. Moving detailed guidance into `docs/` will make both the project entry point and its supporting documentation easier to navigate.

## What Changes

- Reshape the README into a short overview, quick start, and links to detailed documentation.
- Organize service, authentication, development, and deployment guidance in focused pages under `docs/`, preserving existing instructions.
- Skip CI for documentation-only pull requests and their merge pushes, while continuing to run CI when a change includes code or other non-documentation files.

## Capabilities

### New Capabilities
- `ci-workflow`: Define when continuous integration runs for pull requests and pushes to the default branches.

### Modified Capabilities

## Impact

- `README.md` and new files under `docs/`.
- `.gitea/workflows/ci.yml` trigger configuration.
- `openspec/specs/ci-workflow/spec.md` for the CI trigger requirement.
