# Project repository

Canonical GitHub repository: https://github.com/TheoEquity/SAPilot

The `origin` remote for this project should point to this repository.

For SAPilot product goals, SAP domain rules, security constraints, and development guidance, read [`docs/SAPILOT_PROJECT_CONTEXT.md`](docs/SAPILOT_PROJECT_CONTEXT.md). That document distinguishes target behavior from implementation status; treat source code and runtime verification as the authority for current behavior.

For current implementation topics, start with [`docs/zh-CN/design/current/README.md`](docs/zh-CN/design/current/README.md). User-message processing, intent routing, model calls, and Bot/Skill configuration are described in [`docs/zh-CN/design/current/current-architecture-and-message-flow.md`](docs/zh-CN/design/current/current-architecture-and-message-flow.md); general platform architecture is in [`docs/zh-CN/design/current/platform-architecture.md`](docs/zh-CN/design/current/platform-architecture.md). These are static source explanations, not runtime acceptance evidence. Deployment options are indexed in [`docs/README.md`](docs/README.md).

Keep this file limited to working rules and document entry points. Put detailed product background, architecture, message flows, and deployment discussions in the linked documents under `docs/`.

Development, debugging, and routine verification remain local. Cloud servers are for subsequent team deployment and use.

## Discussion drafts

Store discussion drafts under [`docs/zh-CN/design/discussions/`](docs/zh-CN/design/discussions/README.md). Use the [design index](docs/zh-CN/design/README.md) for current explanations, unimplemented plans, historical records, preserved source drafts, test guides, and TODO records. The 18 documents under `pending-review/` retain their original bodies and source-audit notes for traceability; they are no longer the default current-design entry point. Unimplemented plans do not establish current behavior or approval to implement.

- Discussion drafts are discussion records only. During routine implementation and document lookup, do not treat them as an authoritative specification or as evidence of current implementation status.
- When the user explicitly requests implementation based on a particular draft, use that draft as requirements input within the requested scope. The user's current instructions and confirmed decisions take precedence; unresolved proposals, alternatives, and unverified assumptions do not automatically become decisions.
- Establish current behavior from source code, actual configuration, and runtime evidence. Implementing from a draft still requires verification before claiming the work is complete.

## Project layout

Start with [`docs/README.md`](docs/README.md) for documentation and [`docs/zh-CN/reference/project-layout.md`](docs/zh-CN/reference/project-layout.md) for file placement and Git submission rules.

Keep source code, shared documentation and configuration templates in this repository. Local knowledge documents, raw evaluation results, credentials and model weights belong in the sibling `../SAPilot-data/` directory and must not be committed. The existing `models/` directory contains configuration catalogs, not model weights.

Preserve uncommitted work and worktree branches during organization. Verify file hashes and update path references when moving documents. Historical notes are archived under `docs/archive/`; they do not establish current implementation status.
