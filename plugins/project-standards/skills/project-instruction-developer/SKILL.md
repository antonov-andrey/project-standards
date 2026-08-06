---
name: project-instruction-developer
description: Classify or change AGENTS.md, required standards, skill ownership, metadata, references, or instruction models.
---

# Project Instruction Developer

Read `references/instruction-protocol.md` for every instruction task. Read `references/repository-reference.md` when repository paths, links, templates, or cross-owner references are in scope. Read `references/skill-model.md` when skills, plugins, metadata, behavioral evaluation, subagent roles, support owners, or executable standards are in scope.

Treat `Required Standards` as the project-local provider-binding owner. Every governed project declares every exact current `project-standards:*` capability, while each capability applies only when its provider-owned trigger matches current project state or task scope. Add applicable skills from other providers in the same change that introduces their domain. A specialization requires an explicit user decision.

Keep reusable standard prose in its provider, concrete path bindings and project overlays in the governed project, and reusable domain assets in their user-approved domain plugin.

When classification proposes moving one instruction, standard, skill, reference, template, or tool between owners, state explicitly that no move is allowed before the user approves a complete source-to-target ledger. For an approved protected instruction migration, verify every ledger entry and its final semantics directly; do not use prose assertions as a substitute.

When skill descriptions, invocation policy, boundaries, or substantial instructions change, read `references/behavioral-evaluation.md` and validate the provider's versioned behavior corpus through its failed-subset convergence workflow. Use `scripts/skill_behavior_eval.py --list` for deterministic corpus validation and run the model acceptance separately; it does not replace structural validators, pytest, or semantic owner audit.
