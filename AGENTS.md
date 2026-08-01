# Repository Guidelines

## Table Of Contents

- [Required Standards](#required-standards)
- [Project Contract](#project-contract)
- [Key Directory Map](#key-directory-map)
- [Commands](#commands)

## Required Standards

- `project-standards:aws-cloudformation-developer`
- `project-standards:docker-compose-developer`
- `project-standards:http-api-client-developer`
- `project-standards:kubernetes-developer`
- `project-standards:legacy-python-maintainer`
- `project-standards:project-documentation-developer`
- `project-standards:project-foundation`
- `project-standards:project-instruction-developer`
- `project-standards:project-standard-audit`
- `project-standards:pytest-developer`
- `project-standards:python-cli-developer`
- `project-standards:python-developer`
- `project-standards:python-logging-developer`
- `project-standards:python-retry-developer`
- `project-standards:react-ui-developer`
- `project-standards:rest-api-server-developer`
- `project-standards:runtime-config-developer`
- `project-standards:sqlalchemy-developer`
- `project-standards:submodule-developer`
- `project-standards:typescript-developer`
- `project-standards:zitadel-developer`

If one required provider skill is unavailable, continue read-only discovery only and do not mutate this repository until the provider is restored.

## Project Contract

- This repository is the canonical marketplace and plugin owner for reusable cross-domain opinionated project standards.
- Plugin sources live under `plugins/project-standards/`.
- The repository also owns one installable development and test tooling distribution for executable standard checks and shared pytest integration; that distribution is not a Product runtime dependency.
- Each standard is independently triggerable through one capability skill.
- Shared contracts have exactly one owning reference and dependent skills cite that owner instead of copying it.
- Only independently normative closed predicates with complete deterministic implementations qualify as mechanically enforceable checks. They live with the standard's owning skill; one shared runner only discovers and executes them and MUST NOT become a second semantic owner.
- Heuristic signals, selected example lists, semantic inference, and false-positive allowlists are forbidden in executable standard checkers. Requirements that cannot be decided completely stay under mandatory semantic audit.
- Consumer projects declare the complete exact `project-standards` provider catalog through their `AGENTS.md` section `Required Standards`; each declared skill applies only when its provider-owned trigger matches current project state or task scope, and consumer-local generated or copied standard prose is forbidden.
- Domain-specific agent workflows and generic task orchestration do not belong in this repository.

## Key Directory Map

```text
project/
  plugins/
  pyproject.toml
  skill_behavior_eval/
  .spec/
  test/
  .worktree/
  worktree-bootstrap.toml
```

- `plugins/`: provider root for plugin manifests, independently triggerable `Skill`s, shared plugin support owners, and the installable development tooling source.
- `pyproject.toml`: canonical Python distribution, entrypoint, build-asset, dependency, and provider pytest configuration.
- `skill_behavior_eval/`: versioned model-based activation and semantic output-evaluation corpus for this provider.
- `.spec/`: harness-neutral task-artifact root whose reusable semantics are owned by `agent-workflows:goal-brainstorm`.
- `test/`: root behavior-test owner for the installable distribution, runner, scope runtime, and explicit pytest plugin.
- `.worktree/`: task-worktree container whose reusable semantics are owned by `agent-workflows:goal-brainstorm`.
- `worktree-bootstrap.toml`: repository bootstrap-resource binding for the reusable manifest contract owned by `agent-workflows:goal-brainstorm`.

## Commands

- Validate the plugin with `python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/project-standards`.
- Validate every skill with `python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py <skill-root>`.
- Run the workspace inventory with `python plugins/project-standards/skills/project-standard-audit/scripts/workspace_inventory.py --workspace-root <workspace-root> --check`.
- Run changed-scope mechanical checking with `project-standard-check --project-root <repository-root> --scope changed`; use `--scope all` for the complete mechanical scope. Neither command replaces semantic audit.
- Validate or run the provider behavior corpus with `plugins/project-standards/skills/project-instruction-developer/scripts/skill_behavior_eval.py --corpus skill_behavior_eval/corpus-v1.json --list` or the same command without `--list`.
- Run provider tests with `pytest -q`.
