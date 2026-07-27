---
name: project-instruction-developer
description: Use when reading, interpreting, creating, restructuring, auditing, or changing AGENTS.md files, required standards, skill ownership, or repository instruction models.
---

# Project Instruction Developer

Read `references/instruction-protocol.md`, `references/repository-reference.md`, and `references/skill-model.md` completely before changing instructions.

Treat `Required Standards` as the project-local provider-binding owner. Every governed project declares every exact current `project-standards:*` capability, while each capability applies only when its provider-owned trigger matches current project state or task scope. Add applicable skills from other providers in the same change that introduces their domain. A specialization requires an explicit user decision.

Keep reusable standard prose in its provider, concrete path bindings and project overlays in the governed project, and reusable domain assets in their user-approved domain plugin.

For a protected instruction migration, require an approved source-to-target ledger before editing. Verify semantics directly; do not use prose assertions as a substitute.

When skill descriptions, invocation policy, boundaries, or substantial instructions change, validate the provider's versioned behavior corpus with `scripts/skill_behavior_eval.py`. Use `--list` for deterministic corpus validation and run the model phase separately; it does not replace structural validators, pytest, or semantic owner audit.
