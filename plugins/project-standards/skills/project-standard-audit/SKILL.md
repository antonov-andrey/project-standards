---
name: project-standard-audit
description: Use when semantically auditing one repository or workspace for required-standard selection, provider availability, project overlays, duplicated standard prose, tracked task artifacts, or owner-boundary violations.
---

# Project Standard Audit

Read `references/project-standard-audit.md` completely.

Run `project-standardize --check` as mechanical evidence, then inspect each reported repository semantically. Verify every selected standard is applicable, every applicable standard is selected or explicitly excepted, every provider is available, and project-local rules remain genuine overlays.

Report findings with evidence and one recommended correction path. Do not mutate the audited repositories unless the user also asks for implementation.
