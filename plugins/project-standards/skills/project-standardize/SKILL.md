---
name: project-standardize
description: Use when discovering repositories under an explicit workspace root, classifying their applicable project standards, creating minimal project overlays, or checking a workspace standardization migration.
---

# Project Standardize

Read `references/project-standardization.md` completely.

Run `scripts/project_standardize.py --help`, then use an explicit `--workspace-root`. Start with `--check`; do not mutate protected instruction files without an approved source-to-target ledger.

Classify standards from real repository metadata and contents. Preserve project-specific structure, runtime, commands, side effects, security, verification, and explicit exceptions. Do not hardcode a personal workspace path or current repository inventory.
