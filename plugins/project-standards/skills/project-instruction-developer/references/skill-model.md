# Skill Model

- `Skill`
  - Meaning: a `Self-contained` instruction entity rooted either at `plugins/<plugin_name>/skills/<skill_name>/` in its provider repository or at `.agents/skills/<skill_name>/` in the owning project when an explicit user-approved source-to-target decision retains that skill as project-specific.
  - Provider identity: consumers MUST reference one provider `Skill` by its provider-qualified `<plugin_name>:<skill_name>` identity; one retained project-specific `Skill` uses its project-local `<skill_name>` identity only inside its owning project.
  - Canonical contract: `plugins/<plugin_name>/skills/<skill_name>/SKILL.md` for one provider `Skill`, or `.agents/skills/<skill_name>/SKILL.md` for one retained project-specific `Skill`.
  - Frontmatter description: a `Skill` frontmatter description MUST identify both its capability and concrete task triggers in concise direct language; one mandatory boilerplate prefix is forbidden.
  - Owner-local placement: any owner-local artifact of a `Skill` must live under that `Skill` root.
  - Owner-local assets: `test`, `tool`, and other `Skill`-local assets belong to that `Skill`.
  - Ownership limit: a `Skill` must not silently become a generic owner for unrelated repository-wide rules.

## Harness Metadata

- `agents/openai.yaml` exists only when one skill needs meaningful UI metadata, tool dependencies, or invocation policy.
- Generic display names copied from a skill identifier and generic descriptions such as `Help with ... tasks` are forbidden.
- `interface.default_prompt`, when present, MUST contain the exact `$<skill-name>` invocation.
- `interface.short_description`, when present, MUST contain from 25 through 64 characters.
- A skill that must be explicitly invoked sets `policy.allow_implicit_invocation: false`; prose alone does not implement that policy.
- `policy.allow_implicit_invocation: true` is the default and MUST NOT be written without another meaningful metadata field that justifies the file.
- The owner-local metadata checker validates only YAML readability, the exact default-prompt invocation, and the closed short-description length range. Whether metadata is meaningful, current, necessary, or semantically accurate remains a semantic review obligation.

## Behavioral Evaluation

- Provider repositories with overlapping or non-trivial skill triggers MUST keep a versioned activation and output-evaluation corpus.
- The corpus MUST cover direct, indirect, incomplete, negative, and overlap cases, with expected and forbidden activation sets plus semantic output invariants.
- Model-based evaluation is an opt-in acceptance phase separate from deterministic validators, `pytest`, and mechanical standard checkers. It MUST use the target model generation and MUST NOT turn semantic output invariants into substring, heading, or keyword checks.
- The shared runner belongs to `project-instruction-developer/scripts/skill_behavior_eval.py`; provider and retained project-local skills own only their `skill_behavior_eval/corpus-v1.json`.
- A case `working_directory` is relative to its corpus in the repositories' primary sibling layout. When the corpus runs from a linked worktree, a directly present current-worktree path is accepted only when it is on the corpus worktree's same symbolic branch; a missing cross-repository path is mapped through Git worktree registrations to exactly one target worktree on that branch. Missing, wrong-branch, detached, or ambiguous targets fail validation and MUST NOT fall back to target `main`. Git discovery removes inherited repository, index, worktree, namespace, object-directory, and injected-config redirection from the runner subprocess environment.
- One case runs a read-only target-model generation pass against actual discovered instructions and a separate target-model semantic judge pass. Expected activation is a required subset, forbidden activation is exact, and unlisted additional skills are allowed only when genuinely applicable.

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
- The shared runner discovers checker manifests only for capabilities declared by the consumer's complete `Required Standards` catalog; checker discovery MUST NOT create a second applicability map.
- Exact manifest schema, scope strategies, process transport, diagnostics, and failure semantics are owned by root `DESIGN.md`, section `Манифест И Протокол Процесса`.
- Mechanical checker output MUST identify itself as mechanical evidence. Mechanical success does not prove semantic conformance and MUST NOT replace, narrow, seed, or close an applicable semantic audit.
