---
name: project-foundation
description: Use when working in any governed project or when repository ownership, execution integrity, reporting, temporal data, or harness configuration affects the task.
---

# Project Foundation

Read every reference needed by the current scope before acting:

- `references/repository-model.md` for repository entities and ownership;
- `references/writing-and-reporting.md` for prose and problem reports;
- `references/execution.md` for mutation safety, evidence, and verification;
- `references/temporal-data.md` whenever time values or timestamps are involved;
- `references/harness-configuration.md` whenever harness configuration is involved.

Apply the contracts to the real project state. Preserve project-local product, security, structure, runtime, and verification overlays declared by applicable `AGENTS.md` files.

Stop mutation if a required owner is unavailable or if a project-local rule contradicts this provider without an explicit user-authorized specialization.
