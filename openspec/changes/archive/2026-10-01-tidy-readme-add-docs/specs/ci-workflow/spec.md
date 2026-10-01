# Spec Delta

## Purpose

Define when the repository's automated CI workflow runs so documentation-only pull requests and merges do not consume CI resources.

## ADDED Requirements

### Requirement: Skip CI for documentation-only changes
The CI workflow SHALL NOT run for pull requests or pushes to the default branches when every changed file is documentation. The CI workflow SHALL run when a pull request or push includes any non-documentation file. Manual workflow dispatch SHALL remain available.

#### Scenario: Documentation-only pull request
- **WHEN** a pull request changes only Markdown documentation or files under `docs/`
- **THEN** the CI workflow does not run

#### Scenario: Documentation-only merge push
- **WHEN** a push to `main` or `master` contains only Markdown documentation or files under `docs/`
- **THEN** the CI workflow does not run

#### Scenario: Mixed documentation and code changes
- **WHEN** a pull request or push changes documentation and at least one non-documentation file
- **THEN** the CI workflow runs

#### Scenario: Manual CI run
- **WHEN** a user dispatches the CI workflow manually
- **THEN** the CI workflow runs regardless of changed files
