---
name: python-developer
description: Develop, refactor, or review non-Legacy Python code, including scripts, modules, models, functions, classes, imports, naming, and runtime algorithms.
---

# Python Developer

Read these references completely:

- `references/python-code.md`;
- `references/python-core.md`;
- `references/python-refactoring.md`;
- `references/python-naming.md`;
- `references/python-ownership.md`.

Read `references/script-workflow-owner.md` when a bounded algorithm has two or more ordered stages and correctness depends on their handoff or order.

Read `references/code-antipattern-cards.md` only when performing a semantic anti-pattern audit or fixing findings classified by those cards.

Apply `project-foundation` and the more specific capability for CLI, logging, retry, tests, SQLAlchemy, runtime configuration, or HTTP boundaries when those concerns are present.

Do not silently modernize `Legacy`; use `legacy-python-maintainer` for that scope. Preserve the canonical UTC instant contract from `project-foundation/references/temporal-data.md`.
