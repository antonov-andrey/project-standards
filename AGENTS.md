# Repository Guidelines

## Table Of Contents

- [Required Standards](#required-standards)
- [Project Contract](#project-contract)
- [Commands](#commands)

## Required Standards

- `project-standards:project-foundation` applies to all work in this repository.
- `project-standards:project-instruction-developer` applies to instruction artifacts.
- `project-standards:project-documentation-developer` applies to `DESIGN.md` and maintained documentation.
- `project-standards:python-developer`, `project-standards:python-cli-developer`, and `project-standards:pytest-developer` apply to provider tooling and tests.

If one required provider skill is unavailable, continue read-only discovery only and do not mutate this repository until the provider is restored.

## Project Contract

- This repository is the canonical marketplace and plugin owner for reusable cross-domain opinionated project standards.
- Plugin sources live under `plugins/project-standards/`.
- Each standard is independently triggerable through one capability skill.
- Shared contracts have exactly one owning reference and dependent skills cite that owner instead of copying it.
- Consumer projects select applicable skills through their `AGENTS.md` section `Required Standards`; consumer-local generated or copied standard prose is forbidden.
- Domain-specific agent workflows and generic task orchestration do not belong in this repository.
- Active task pairs live only under the ignored `.spec/` root.

## Commands

- Validate the plugin with `python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/project-standards`.
- Validate every skill with `python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-root>`.
- Run provider tests with `pytest -q`.
