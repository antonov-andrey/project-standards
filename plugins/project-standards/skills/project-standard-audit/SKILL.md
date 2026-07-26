---
name: project-standard-audit
description: Use when semantically auditing one repository or workspace for required-standard selection, provider availability, project overlays, duplicated standard prose, tracked task artifacts, or owner-boundary violations.
---

# Project Standard Audit

Read `references/project-standard-audit.md` completely.

Run the `project-standards:project-standardize` owner command `<project-standardize-skill-root>/scripts/project_standardize.py --workspace-root <workspace-root> --check` and `project-standard-check --project-root <repository-root> --scope all` as the separate mechanical phase. Treat their output only as mechanical evidence.

Build the semantic phase independently from the complete current owner set, never from checker identities, checker findings, previously noticed concerns, or a prior audit. Enumerate every selected provider rule family, every project-local normative section, every mapped owner path, every referenced design boundary, and every candidate applicable provider not yet selected. Give each requirement one semantic verdict with current evidence or one explicit not-applicable reason.

A clean result is forbidden while any owner, rule family, requirement, path binding, selection decision, or source-to-target ledger entry lacks semantic coverage. When implementation is authorized, fix all findings, rerun applicable mechanical verification, then restart the complete semantic audit from owner discovery. Repeat until a fresh full audit produces no new findings.

Report findings with evidence and one recommended correction path. Do not mutate the audited repositories unless the user also asks for implementation.
