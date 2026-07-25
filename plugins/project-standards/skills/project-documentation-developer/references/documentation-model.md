# Documentation Model

- `Main project documentation`
  - Meaning: stable project documentation whose owners are `DESIGN.md`, `design/**`, and `docs/**`.
  - Membership: it includes stable architecture and domain design, operational catalogs, project-local operational workflows, user and reference documentation, and other long-lived human-readable guidance maintained outside instruction and task artifacts.
  - Exclusions: it does not include `Main project AGENTS.md`, `Main project code`, `test`, `tool`, or `.spec` task artifacts.
  - Repository-wide rules owner: `project-standards:project-documentation-developer`.

- `.spec`
  - Meaning: one ignored harness-neutral root for task pairs regardless of task state.
  - Pair shape: `.spec/YYYY-MM-DD-<semantic-name>-spec.md` and `.spec/YYYY-MM-DD-<semantic-name>-goal.md`.
  - Git boundary: the repository MUST use the exact root-level ignore rule `/.spec/`, and files under `.spec/` MUST remain untracked.
  - Lifecycle: task pairs are retained after every state transition, including completion or abandonment, and MUST NOT be deleted unless the user explicitly requests their deletion.
  - Boundary: a multi-repository task keeps one pair in its coordinating repository.
