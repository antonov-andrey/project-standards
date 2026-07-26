---
name: project-standardize
description: Use when discovering repositories under an explicit workspace root, collecting exact mechanical standard metadata, or preparing and checking a workspace standardization migration with mandatory semantic classification.
---

# Project Standardize

Read `references/project-standardization.md` completely.

Run `scripts/project_standardize.py --help`, then use an explicit `--workspace-root` and `--check`. The script is read-only and reports only mechanical inventory, including exact equality between each declared `project-standards:*` set and the current provider catalog; it does not classify technology applicability or write `Required Standards`.

After the mechanical inventory, perform the complete semantic classification defined by `project-standard-audit`: inspect every repository entity, technology, boundary, artifact family, workflow, conditionally applicable provider contract, and project-local overlay. Do not derive semantic scope from script output. Preserve project-specific structure, runtime, commands, side effects, security, verification, and explicit exceptions. Do not hardcode a personal workspace path or current repository inventory.

When implementation is requested, apply only the approved source-to-target ledger, rerun the mechanical inventory, and restart a complete semantic audit until a fresh pass has no findings.
