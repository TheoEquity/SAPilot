# Project repository

Canonical GitHub repository: https://github.com/TheoEquity/SAPilot

The `origin` remote for this project should point to this repository.

For SAPilot product goals, SAP domain rules, security constraints, and development guidance, read [`docs/SAPILOT_PROJECT_CONTEXT.md`](docs/SAPILOT_PROJECT_CONTEXT.md). That document distinguishes target behavior from implementation status; treat source code and runtime verification as the authority for current behavior.

For current implementation topics, user-message processing, intent routing, model calls, and Bot/Skill configuration are described in [`docs/design/zh-CN/current/current-architecture-and-message-flow.md`](docs/design/zh-CN/current/current-architecture-and-message-flow.md); general platform architecture is in [`docs/design/zh-CN/current/platform-architecture.md`](docs/design/zh-CN/current/platform-architecture.md). These are static source explanations, not runtime acceptance evidence.

Keep this file limited to working rules and direct document references. Keep architecture, development conventions, and environment guidance in `docs/specs/`; product explanations and discussion drafts in `docs/`; implementation and verification records in `docs/records/`.

Development, debugging, and routine verification remain local. Cloud servers are for subsequent team deployment and use.

## Engineering architecture and maintenance

Architecture, conventions, and environment guidance live in `docs/specs/`. For development and maintenance tasks, read the [development workflow and shared-change boundaries](docs/specs/development-workflow.md), then the relevant topic:

- [High-level engineering architecture](docs/specs/engineering-architecture.md): module responsibilities, layers, dependencies, and boundaries; endpoint details belong in OpenAPI definitions.
- [Frontend conventions](docs/specs/frontend-architecture-and-conventions.md): file placement, UI, state, effects, and verification.
- [Backend conventions](docs/specs/backend-architecture-and-conventions.md): Service, Agent, storage, and background-task maintenance.
- [Full-stack logging and diagnostics](docs/specs/logging-and-diagnostics.md): frontend, API, worker and model/tool events, correlation, redaction, and failure investigation.
- [Database design and migrations](docs/specs/database-design-conventions.md): tables, fields, constraints, indexes, and migration verification.
- [API contract maintenance](docs/specs/api-contract-conventions.md): Python-owned FastAPI routes and models, generated documentation and frontend clients, and protocol boundaries.
- [Development environment guide](docs/specs/development-guide.md): local environment setup, startup, and development commands.

Follow current user instructions and existing authorization. Verify actual behavior from source, configuration, and runtime evidence; keep changes within the requested scope.

README files provide explanations, overviews, and navigation only. They are not development instruction sources, approval rules, or mandatory workflow steps. Maintain development requirements in this file and the specific documents linked above, without routing those requirements through a README.

## Discussion drafts

- Store discussion drafts in `docs/design/zh-CN/discussions/`; process plans and execution records belong in `docs/records/`. Drafts record discussion, not approved requirements or implemented behavior.
- Use a draft as requirements only when the user explicitly requests it, within the requested scope. Current instructions and confirmed decisions take precedence.
- Verify current behavior and completion against source code, actual configuration, and runtime evidence.

## Project layout

For file placement and Git submission rules, read [`docs/specs/project-layout.md`](docs/specs/project-layout.md).

Keep business source under `app/`, maintenance-tool setup under `maintenance/`, and shared documentation under `docs/` in this repository. Local knowledge documents, raw evaluation results, credentials and model weights belong in the local ignored `data/` and `runtime/` directories and must not be committed. The existing `app/models/` directory contains configuration catalogs, not model weights.

Preserve uncommitted work and worktree branches during organization. Verify file hashes and update path references when moving documents. Historical notes are archived under `docs/archive/`; they do not establish current implementation status.
