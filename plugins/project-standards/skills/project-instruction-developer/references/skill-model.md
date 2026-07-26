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

## Executable Standard Ownership

- A capability `Skill` that owns one mechanically enforceable standard subset MAY declare one owner-local `<skill-root>/checker.toml`.
- One mechanically enforceable subset is eligible only when it is an independently normative closed predicate and its checker is one complete deterministic decision procedure over the entire declared scope.
- A checker MUST NOT infer intent, semantics, applicability, ownership, necessity, quality, or exceptions from selected names, paths, examples, thresholds, allowlists, or smell signals. A finite set is allowed only when the normative rule itself defines that exact exhaustive set.
- When a rule cannot satisfy that eligibility contract, it remains entirely semantic and MUST NOT have one approximate checker. Passing samples or suppressing false positives does not make an approximation eligible.
- `<skill-root>/checker.toml` identifies only checker scripts owned under that same skill root. It MUST NOT restate semantic rules, consumer-specific exceptions, or project-local paths.
- Checker implementation, samples, and checker behavior tests remain under the owning skill root. A second skill MUST reference or reuse the real owner instead of copying its checker.
- Shared checker discovery, scope resolution, process execution, and diagnostic protocol belong to one plugin support owner under `plugins/project-standards/lib/project_standards/`.
- The shared runner discovers checker manifests only for capabilities already selected by the consumer's `Required Standards`; checker discovery MUST NOT create a second standard-selection map.
- Exact manifest schema, scope strategies, process transport, diagnostics, and failure semantics are owned by root `DESIGN.md`, section `Манифест И Протокол Процесса`.
- Mechanical checker output MUST identify itself as mechanical evidence. Mechanical success does not prove semantic conformance and MUST NOT replace, narrow, seed, or close an applicable semantic audit.
