# Project Standardization

## Discovery

- Require one explicit workspace root.
- Discover immediate child Git worktrees through either a `.git` directory or a `.git` file.
- Read repository metadata and tracked paths from Git. Do not hardcode repository names, personal home paths, or a current workspace inventory.
- Treat secondary worktrees as repositories for checking, but do not edit two worktrees of the same Git common directory in one run.

## Classification

- Always select `project-foundation` and `project-instruction-developer`.
- Select other capabilities from actual tracked entities, technologies, boundaries, artifact families, and workflows.
- A missing applicable capability is a validation failure unless the project records an explicit user-authorized exception.
- Do not infer application modernization from classification. Existing unmodeled Python remains `Legacy` until an explicit migration changes its owner.
- Do not select a capability only for symmetry.

## Mutation

- Read-only check is the default safe operation.
- Write mode changes only `Required Standards`, preserving every other project-local instruction.
- Create no generated copy of provider prose and no separate project-standard manifest.
- Do not modify an existing instruction artifact marked or known as a protected migration without its approved source-to-target ledger.
- Fail before writing if a required provider skill is unavailable.

## Verification

- Report repository path, Git common directory, detected capabilities, declared capabilities, missing capabilities, unavailable providers, and duplicate common-directory worktrees.
- Re-run check after write mode.
- Semantic audit remains required; classifier output is mechanical evidence only.
