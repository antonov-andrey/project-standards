# Documentation Scope And Workflow

- Stable project architecture and domain design belong in `DESIGN.md` or `design/**`.
- User, operational, and other maintained documentation that is not a stable design contract belongs under `docs/**`.
- A project-specific implementation contract belongs in `DESIGN.md` or `design/**` when it defines stable architecture or domain design, and in `AGENTS.md` when it defines durable normative engineering instructions.
- A reusable cross-project implementation pattern MUST belong to its applicable `project-standards` capability skill instead of being copied into consumer projects.
- Code changes MUST update documentation only when they change a stable documented architecture, operational fact, script lifecycle rule, run or test exception, or maintained project workflow.
- Documentation updates required by a code change MUST happen before handoff verification.
- Create a retained target and verify complete semantic preservation before deleting or moving its source.
- Do not leave forwarding documents, compatibility paths, simultaneous old and new owners, empty roots created for symmetry, or task history in tracked documentation. Apply the `.spec` retention and deletion contract from `references/documentation-model.md` to ignored task pairs.
