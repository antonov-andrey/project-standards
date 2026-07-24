# Skill Model

- `Skill`
  - Meaning: a `Self-contained` instruction entity rooted either at `plugins/<plugin_name>/skills/<skill_name>/` in its provider repository or at `.codex/skills/<skill_name>/` in the owning project when an explicit user-approved source-to-target decision retains that skill as project-specific.
  - Provider identity: consumers MUST reference one provider `Skill` by its provider-qualified `<plugin_name>:<skill_name>` identity; one retained project-specific `Skill` uses its project-local `<skill_name>` identity only inside its owning project.
  - Canonical contract: `plugins/<plugin_name>/skills/<skill_name>/SKILL.md` for one provider `Skill`, or `.codex/skills/<skill_name>/SKILL.md` for one retained project-specific `Skill`.
  - Frontmatter description: a `Skill` frontmatter description MUST start with `Use when ...` and MUST describe concrete task triggers in direct language.
  - Owner-local placement: any owner-local artifact of a `Skill` must live under that `Skill` root.
  - Owner-local assets: `test`, `tool`, and other `Skill`-local assets belong to that `Skill`.
  - Ownership limit: a `Skill` must not silently become a generic owner for unrelated repository-wide rules.

## Role Contracts

Every workflow-owned subagent role contract MUST state the role mission, scope, limits, evidence requirements, and handoff rules. A workflow MUST express that contract through its provider-owned task prompt or template and adapt execution to the available harness capabilities. Consumer-local named-agent TOML MUST NOT be the canonical or required cross-harness representation of a subagent role.

## Plugin Support Owners

One provider path `plugins/<plugin_name>/lib/<owner>/` is a `Self-contained` plugin-local owner for shared workflow or subagent protocols, Markdown contracts, templates, handoff assets, state-machine or algorithm specifications, and owner-local `tool` or `test`; every owner-local asset MUST remain under that owner root.
