# Project Standardization

## Discovery

- Require one explicit workspace root.
- Discover immediate child Git worktrees through either a `.git` directory or a `.git` file.
- Read repository metadata and tracked paths from Git. Do not hardcode repository names, personal home paths, or a current workspace inventory.
- Treat secondary worktrees as repositories for checking, but do not edit two worktrees of the same Git common directory in one run.

## Mechanical Inventory

- Mechanically verify root `AGENTS.md` presence, the closed baseline selection of `project-foundation` and `project-instruction-developer`, availability of every declared provider, the exact task-root ignore contract, absence of tracked `.spec` artifacts, and duplicate Git common-directory worktrees.
- Table-of-contents structure, instruction meaning, applicability wording, and semantic completeness are outside the script and MUST be audited semantically.
- Report these results only as mechanical inventory.
- Do not inspect imports, filenames, dependencies, manifests, prose tokens, or selected framework examples to infer applicable standards.
- Do not produce a mechanically inferred `required_standard_list`, `missing_standard_list`, or whole-project validity verdict.

## Semantic Classification

- Select capabilities from a complete semantic inspection of actual tracked entities, technologies, boundaries, artifact families, workflows, instructions, and stable design.
- Inspect every available capability family for applicability; do not limit discovery to capabilities suggested by the mechanical inventory or previously observed project patterns.
- A missing applicable capability is a finding unless the project records an explicit user-authorized exception.
- Existing unmodeled Python remains `Legacy` until an explicit migration changes its owner.
- Do not select a capability only for symmetry.
- Do not modify a protected instruction artifact without its approved source-to-target ledger.
- After any fix, restart the complete semantic classification from repository and provider discovery.

## Verification

- Report repository path, Git common directory, declared capabilities, baseline omissions, unavailable providers, missing root instructions, task-root findings, and duplicate common-directory worktrees.
- Output `mechanical_status` and `semantic_audit_required=true`; never output `is_valid` for whole-project conformance.
- Run the mechanical inventory and complete semantic audit in every standardization acceptance. Neither phase replaces the other.
