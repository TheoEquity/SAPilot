# Project repository

Canonical GitHub repository: https://github.com/TheoEquity/SAPilot

The `origin` remote for this project should point to this repository.

For SAPilot product goals, SAP domain rules, security constraints, and development guidance, read [`docs/SAPILOT_PROJECT_CONTEXT.md`](docs/SAPILOT_PROJECT_CONTEXT.md). That document distinguishes target behavior from implementation status; treat source code and runtime verification as the authority for current behavior.

## Project layout

Start with [`docs/README.md`](docs/README.md) for documentation and [`docs/zh-CN/reference/project-layout.md`](docs/zh-CN/reference/project-layout.md) for file placement and Git submission rules.

Keep source code, shared documentation and configuration templates in this repository. Local knowledge documents, raw evaluation results, credentials and model weights belong in the sibling `../SAPilot-data/` directory and must not be committed. The existing `models/` directory contains configuration catalogs, not model weights.

Preserve uncommitted work and worktree branches during organization. Verify file hashes and update path references when moving documents. Historical notes are archived under `docs/archive/`; they do not establish current implementation status.
