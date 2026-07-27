# Workspace Inventory

## Discovery

- Require one explicit workspace root.
- Discover immediate child Git worktrees through either a `.git` directory or a `.git` file.
- Read repository metadata and tracked paths from Git. Do not hardcode repository names, personal home paths, or a current workspace inventory.
- Treat secondary worktrees as repositories for checking, but do not edit two worktrees of the same Git common directory in one run.

## Mechanical Inventory

- Mechanically verify root `AGENTS.md` presence and exact set equality between declared `project-standards:*` capabilities and the current provider catalog.
- Report duplicate Git common-directory worktrees as inventory evidence. Their existence is not a finding by itself; mutation of two such worktrees in one run is forbidden and belongs to execution-scope control.
- Table-of-contents structure, instruction meaning, applicability wording, and semantic completeness are outside the script and MUST be audited semantically.
- Report these results only as mechanical inventory.
- Do not inspect imports, filenames, dependencies, manifests, prose tokens, or framework examples to infer applicable standards.
- Do not produce a mechanically inferred `required_standard_list`, `missing_standard_list`, or whole-project validity verdict.

## Output

- Report the current `available_project_standard_list`, repository path, Git common directory, `declared_project_standard_list`, `missing_project_standard_list`, `unavailable_project_standard_list`, missing root instructions, and duplicate common-directory worktrees.
- Output `mechanical_status` and `semantic_audit_required=true`; never output `is_valid` for whole-project conformance.
- Hand the inventory to the separate semantic phase without using it to derive semantic scope.
