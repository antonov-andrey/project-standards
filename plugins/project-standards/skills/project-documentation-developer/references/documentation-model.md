# Documentation Model

- `Main project documentation`
  - Meaning: stable project documentation whose owners are `DESIGN.md`, `design/**`, and `docs/**`.
  - Membership: it includes stable architecture and domain design, operational catalogs, project-local operational workflows, user and reference documentation, and other long-lived human-readable guidance maintained outside instruction and active task artifacts.
  - Exclusions: it does not include `Main project AGENTS.md`, `Main project code`, `test`, `tool`, or `.spec` task artifacts.
  - Repository-wide rules owner: `project-standards:project-documentation-developer`.

- `.spec`
  - Meaning: one ignored harness-neutral root for active or unclassified task pairs.
  - Pair shape: `.spec/YYYY-MM-DD-<semantic-name>-spec.md` and `.spec/YYYY-MM-DD-<semantic-name>-goal.md`.
  - Lifecycle: completed or abandoned pairs are removed after durable requirements reach stable owners; active, blocked, paused, or unclassified pairs are preserved.
  - Boundary: a multi-repository task keeps one pair in its coordinating repository.
