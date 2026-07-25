---
name: python-developer
description: Use when writing, refactoring, reviewing, or structurally changing non-Legacy Python code, packages, models, functions, classes, imports, naming, or runtime algorithms.
---

# Python Developer

Read these references completely:

- `references/python-code.md`;
- `references/python-core.md`;
- `references/python-refactoring.md`;
- `references/python-naming.md`;
- `references/python-ownership.md`.

Read `references/script-workflow-owner.md` when a bounded algorithm has two or more ordered stages and correctness depends on their handoff or order.

Apply `project-foundation` and the more specific capability for CLI, logging, retry, tests, SQLAlchemy, runtime configuration, or HTTP boundaries when those concerns are present.

Do not silently modernize `Legacy`; use `legacy-python-maintainer` for that scope. Preserve the canonical UTC instant contract from `project-foundation/references/temporal-data.md`.
