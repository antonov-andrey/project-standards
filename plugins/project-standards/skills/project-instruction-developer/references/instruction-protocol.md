# Instruction Protocol

### Instruction Protocol Terms
- `Explicit entity-local specialization` means an owner-local slice of a named term whose allowed relationships are stated separately from the parent term in `Allowed Dependency Matrix`.
- `Repository-wide definition rule` means a standalone top-level repository-wide rule family that extends one named `Core Term` beyond its core definition.

### Section Placement Rules
- Every normative statement in the governed AGENTS.md file MUST belong to exactly one owner section.
- Definitions of named repository terms that apply outside one top-level section belong only in `Core Terms`.
- Definitions of named standard `Submodule`s belong only in `Standard Submodule List`.
- A top-level section MAY define section-local terms only in its first subsection named `{Section} Terms`, and that subsection owns only section-local terms for its own top-level section.
- Path-to-term mapping and simple path-level nodes whose semantics are defined only by their literal project paths belong only in `Key Directory Map`.
- Allowed relationships between named terms and `Explicit entity-local specialization`s belong only in `Allowed Dependency Matrix`.
- Standalone `Repository-wide definition rule`s for one named `Core Term` belong only in their dedicated top-level rule sections.
- Repository-wide operational rules that are neither definitions, nor path mappings, nor dependency rules belong only in their appropriate non-definition sections.
- If one statement mixes multiple owner types, split it into separate statements and place each statement under its own owner section.

### Cross-Definition Rules
- `project-standards:project-instruction-developer` is the single owner of repository-wide structure, placement, and boundary semantics in the governed AGENTS.md instruction model.
- `agent-workflows:instruction-audit` is the canonical owner of semantic audit workflow for instruction artifacts modeled by the governed AGENTS.md instruction model; that skill MUST follow `Instruction Protocol` instead of redefining it.
- Read the structure model from path ownership first, before style, workflow, or class-shape rules.
- Each mapped path family or path-level owner node remains a distinct structure entity with its own allowed responsibilities even when several such entities live in one project.
- Root coordination across entities does not collapse those boundaries.
- Canonical `AGENTS.md` precedence MUST follow this boundary model:
  - within one repository boundary, a nearer canonical `AGENTS.md` MAY only clarify, narrow, or specialize its applicable parent chain and MUST NOT contradict it,
  - for paths inside one `Submodule`, the applicable `Main project AGENTS.md` chain and the applicable `Submodule AGENTS.md` chain coexist,
  - when those chains conflict on a path inside that `Submodule`, the applicable `Submodule AGENTS.md` chain has priority for that `Submodule` path.
- Named `Core Terms`, named standard `Submodule`s, and terms defined in a `{Section} Terms` subsection MUST be written in backticks whenever they are referenced as named entries within their allowed scope.
- Terms defined in a `{Section} Terms` subsection MUST be used only inside that top-level section.
- If a section-local term starts being used outside its owning top-level section, remove it from that section-local term owner immediately: move it to an enclosing higher-level `{Section} Terms` subsection when one exists; otherwise move it to `Core Terms`.
- If a path family, artifact family, repository concept, or concrete standard `Submodule` already has a named owner in `Core Terms` or `Standard Submodule List`, later sections MUST use that name instead of restating the path unless the path is explicitly required to define directory ownership, a canonical owner location, an artifact taxonomy, or a verification target.
- Later sections MAY apply a named `Core Term` or named standard `Submodule` to a specific owner root, workflow, or verification target, but they MUST NOT become a second definition owner for that named entry.
- Equivalent normative semantics remain duplicates regardless of wording changes, including operational paraphrase.
- Normative wording in the governed AGENTS.md instruction model MUST be clear, unambiguous, and directly understandable; undefined shorthand, informal weakening phrasing, and wording that permits multiple reasonable interpretations are forbidden.
- Normative wording MUST be no more detailed than needed to define the owned rule; unnecessary qualifiers, explanatory restatements, and non-exhaustive case lists are forbidden when shorter wording preserves the same semantics.
- When one owner depends on details owned elsewhere, reference that owner instead of restating those details unless one narrower owner-local trigger, boundary, or transition must be defined locally.
- Workflow and state-machine steps MUST contain only step-local actions and transitions; repeated requirements from other contracts belong only in their owning contract.

### Core Terms Rules
- `Core Terms` MUST contain only repository concepts that are not adequately defined by one self-explanatory literal path or one self-explanatory path template.
- A concept belongs in `Core Terms` when it spans multiple owner roots or repository entities, depends on inclusion/exclusion logic instead of one path family, or needs boundary semantics beyond a raw path.
- `Core Terms` MUST NOT absorb section-local terms that are used only inside one top-level section.
- Do not add named `Core Terms` for one-off self-descriptive paths such as `.codex/config.toml`.
- Each term block in `Core Terms` MUST be the single authoritative and complete owner of that term's defining semantics inside the governed AGENTS.md instruction model, even when a separate dedicated rule section extends its repository-wide usage rules.

### Key Directory Map Rules
- `Key Directory Map` MUST stay complete at this path-level detail for every currently modeled root path family, path-level owner node, and simple path-level node in the structure model.
- Every `Key Directory Map` tree node MUST use exactly one of these terminal shapes: a file-like path without a trailing slash, or a directory-like path with a trailing slash.
- Within each parent block, `Key Directory Map` tree lines and explanatory bullets MUST be alphabetically sorted by path label, ignoring notation-only wildcard, placeholder, or leading-dot prefixes, and both representations MUST use the same order.
- Simple path-level nodes that are not named `Core Terms` but carry unique ownership, placement, or structural semantics, such as `.codex/config.toml`, `docs/script_catalog.md`, `test/integration/`, or `tool/lib/`, MUST still appear in `Key Directory Map`.
- Each modeled owner path, simple path-level node, or composite path template represented by `Key Directory Map` MUST have exactly one explanatory bullet immediately below the map, and that bullet MUST be the single authoritative owner of the path-specific semantics for that modeled node in the governed AGENTS.md instruction model.
- When one `Key Directory Map` bullet maps a concrete standard `Submodule` root to its named owner in `Standard Submodule List`, that bullet MUST own only the path mapping and MUST NOT own that `Submodule`'s defining semantics.
- Purely structural parent lines inside the tree that only group child paths do not require their own explanatory bullet unless they carry semantics of their own.
- Later sections MAY reference a path from `Key Directory Map` when needed, but they MUST NOT restate or redistribute that path's path-specific semantics outside the owning `Key Directory Map` bullet.
- Later sections MAY add non-structural operational obligations that reference one mapped path when those obligations are owned by the later section and the `Key Directory Map` bullet remains the only owner of that path's structural semantics.

### Allowed Dependency Matrix Rules
- `Allowed Dependency Matrix` MUST list every named source whose dependency targets are intentionally restricted by the governed AGENTS.md instruction model beyond the explicit prohibitions owned elsewhere in the governed AGENTS.md instruction model.
- `Allowed Dependency Matrix` governs only named terms and `Explicit entity-local specialization`s; simple path-level nodes such as `.codex/config.toml` are outside this matrix unless they are promoted in the governed AGENTS.md as named entries.
- When a named term or `Explicit entity-local specialization` has no dedicated row in `Allowed Dependency Matrix`, this matrix imposes no dependency restrictions on that source.
- When a source has a dedicated row in `Allowed Dependency Matrix`, that row is the single owner of that source's dependency restrictions inside this matrix unless the row explicitly says otherwise.
- A source with a dedicated row in `Allowed Dependency Matrix` MAY depend on itself unless that row explicitly says otherwise.
- Unless a source's dedicated row explicitly says otherwise, that source MUST NOT depend on another entity's owner-local `test`, `tool`, or other artifacts.

### Repository-wide Definition Rules
- A standalone top-level dedicated rule section for a named term MUST extend that already fully defined term and MUST NOT become a second owner of the term's definition.
- A standalone top-level dedicated rule section owns only repository-wide rules for how that already fully defined term is used in the governed project repository.
- If a named term has a standalone top-level dedicated rule section, that term's block in `Core Terms` MUST contain one explicit hard reference naming that rule section as the single owner of repository-wide rules for that term.
- If repository-wide usage rules for a term need more than five top-level bullets beyond that term's defining semantics, move those rules into a standalone top-level dedicated `{Term} Rules` section instead of extending the term definition block.
- If a standalone top-level dedicated `{Term} Rules` section no longer needs more than five top-level repository-wide usage-rule bullets beyond that term's defining semantics, delete that section and move those remaining rules back into the term's block in `Core Terms`.

### Main Project AGENTS.md Structure Rules
- The repository-root canonical `AGENTS.md` in `Main project AGENTS.md` MUST follow this table-of-contents contract:
  - keep a complete `Table Of Contents` immediately after the H1 title,
  - keep that `Table Of Contents` as the first level-2 section,
  - enumerate every later level-2 and level-3 heading in document order,
  - use `- [Heading](#anchor)` for level-2 TOC entries and `  - [Heading](#anchor)` for level-3 TOC entries,
  - derive TOC anchors from the literal heading text by lowercasing it, removing non-alphanumeric punctuation, and replacing spaces with hyphens.

## External Standard Reference Rules

- `Required Standards` is the single project-local owner of external provider bindings for one governed `AGENTS.md`.
- Its canonical machine-readable section heading MUST be exactly `## Required Standards`.
- Every provider declaration in `Required Standards` MUST be one top-level Markdown bullet beginning with `- ` and name each provider-qualified skill in inline code. One bullet MAY group skills that share one project-local applicability statement.
- Every governed project MUST declare every exact current `project-standards:*` capability exposed by the installed provider.
- Declaring the complete `project-standards` catalog binds the project to that provider and MUST NOT be interpreted as a claim that every governed technology or entity already exists in the project.
- Each declared `project-standards:*` capability applies only when its provider-owned `Use when` trigger matches current project state or task scope; consumer instructions MUST NOT copy that applicability prose or maintain a second selection map.
- When a new `project-standards:*` capability is added to the provider, every governed project MUST add its exact identity before its mechanical catalog check can pass.
- When a project introduces an entity already covered by a declared `project-standards:*` capability, that capability applies in the same change without another `Required Standards` edit.
- Provider-qualified skills outside `project-standards` MUST be added to `Required Standards` when their provider-owned trigger becomes applicable to current or newly introduced project state.
- Standard applicability MUST be derived from the current project state and task scope; it is a requirement, not an optional recommendation.
- Agent inference, project-local convenience, existing non-compliance, or the absence of a previous non-`project-standards` provider entry MUST NOT create an applicability exception.
- If one required provider or skill is unavailable, read-only discovery MAY continue, but project mutation MUST stop until the required owner is available.
- A project-local rule MAY narrow or specialize an external standard only when an explicit user requirement authorizes that specialization and the rule names the provider-qualified skill, exact external owner, and local scope.
- One authorized project-local specialization has precedence only inside its declared local scope.
- An unmarked contradiction between a project-local rule and a required external standard is invalid and MUST block project mutation until the conflict is resolved.
- Project-local `AGENTS.md` MUST NOT copy, paraphrase, generate, or materialize external standard prose.
- A `Core Terms` definition owned by a required provider-qualified skill is part of the governed `AGENTS.md` instruction model within that skill's provider-owned applicability scope.
- A governed `AGENTS.md` MAY reference such a named term without copying its definition.
- The provider-owned term block remains the single authoritative and complete definition owner across the governed instruction model.
- Project-local `Core Terms` MUST contain only project-specific terms that are not already defined by an applicable required standard.
- A project-local `AGENTS.md` MUST NOT restate or redefine a provider-owned term.
- If two applicable required standards define the same term incompatibly, project mutation MUST stop until the provider ownership conflict is resolved.
- An explicitly user-authorized project-local specialization MAY extend the use of a provider-owned term inside its declared local scope, but MUST NOT become a second definition owner.

## Domain Plugin Ownership Rules

- A reusable agent asset is domain-specific when its triggers, vocabulary, decisions, contracts, or tools depend on one business or platform domain and are not valid as a general task workflow or cross-domain engineering standard.
- Reusable domain-specific skills, references, templates, tools, and tests MUST belong to one independently installable plugin dedicated to that coherent domain.
- One coherent domain MUST use one canonical domain plugin instead of creating provider copies per consumer project, per repository, per vendor endpoint, or per task.
- A domain plugin MUST expose its reusable contract through one or more independently triggerable domain skills; an empty plugin or a plugin with no skill entrypoint is forbidden.
- When a reusable domain asset appears and a canonical plugin for that domain already exists, the asset MUST be added to that plugin.
- When a reusable domain asset appears and no canonical plugin for that domain exists, a domain plugin MUST be created before consumer-local copies are published or retained as the reusable owner.
- Classification of each skill, reference, template, or agent tool as project-local or reusable domain-specific MUST follow an explicit user-approved source-to-target decision; consumer count, potential future reuse, and agent inference MUST NOT make that decision.
- When the user classifies one asset as reusable domain-specific, that asset MUST move to the canonical domain plugin; when the user classifies it as project-specific, it MUST remain with its project owner.
- Generic task procedures and orchestration belong to `agent-workflows`.
- Cross-domain opinionated engineering standards belong to `project-standards`.
- Reusable workflow-container domain assets explicitly assigned by the user to a shared provider belong to `workflow-container-agent-tools`.
- Reusable marketplace domain assets explicitly assigned by the user to a shared provider belong to `marketplace-agent-tools`.
- A domain plugin MUST reference applicable generic workflow and engineering owners instead of copying their contracts.
- Stable runtime provider design remains in the provider repository `DESIGN.md`; application-specific business behavior, paths, configuration, data, and executable runtime logic remain with the owning project unless the domain plugin owns a real reusable agent tool.
- A domain plugin name MUST identify both its domain and agent-tool role and MUST NOT collide with an active application repository, marketplace source, or another plugin identifier.
- Every domain plugin identifier MUST use the common `<domain>-agent-tools` shape; a different suffix or a suffixless domain plugin identifier is forbidden unless the user explicitly changes this naming contract.
- If an applicable domain plugin or required domain skill is unavailable, read-only discovery MAY continue, but mutation of the governed domain scope MUST stop until the provider is available.
- Omitting, replacing, or bypassing an applicable domain plugin is allowed only by an explicit user requirement.

## Main project AGENTS.md

- `Main project AGENTS.md`
  - Meaning: the repository-root canonical `AGENTS.md` file together with canonical nested `Main project AGENTS.md` files outside `Submodule` roots.
  - Applicability: `AGENTS.md` application is path-scoped, and the repository-root canonical `AGENTS.md` applies by default to the whole repository including `Submodule`s.
  - Precedence: for any path in the `Main project` repository boundary, apply every applicable canonical `Main project AGENTS.md` on the directory chain from the repository root to that path; each nearer file may only clarify, narrow, or specialize its applicable parent instructions for its own subtree and MUST NOT contradict them, and for paths inside one `Submodule` this applicable `Main project AGENTS.md` chain remains applicable but yields to the applicable `Submodule AGENTS.md` chain on conflict.

## Submodule AGENTS.md

- `Submodule AGENTS.md`
  - Meaning: every `AGENTS.md` file inside one `<submodule_root>/` tree, including `<submodule_root>/AGENTS.md` and any deeper nested `AGENTS.md`.
  - Boundary role: `Submodule AGENTS.md`, when present, defines the local boundary model inside that `Submodule`.
  - Scope limit: `Submodule AGENTS.md` must not redefine root repository ownership outside the `Submodule`.
  - Language override owner: `Submodule` language overrides belong to `Submodule AGENTS.md`.
  - Local precedence role: when `<submodule_root>/AGENTS.md` exists, it is the root of the local canonical `Submodule AGENTS.md` chain for paths inside that `Submodule`; otherwise the nearest applicable deeper canonical `AGENTS.md` inside that same `Submodule` starts the applicable `Submodule AGENTS.md` chain for its own subtree; nested canonical `AGENTS.md` files inside that same `Submodule` may only clarify, narrow, or specialize their applicable `Submodule AGENTS.md` parent and MUST NOT contradict it, and conflicts between the applicable `Main project AGENTS.md` chain and the applicable `Submodule AGENTS.md` chain for a path inside that `Submodule` MUST be resolved in favor of the `Submodule AGENTS.md` chain.

## External Path Reference Rules

- A project-local `Key Directory Map` is the single owner of concrete project path bindings and project-specific path semantics.
- When reusable semantics of a mapped path are owned by a required provider-qualified skill, the local explanatory bullet MUST name that exact owner and MUST NOT copy or paraphrase its contract.
- Every current concrete owner root and every project-local path template used by the project MUST remain represented in the local map.
- A generic placeholder path that is neither used by a current project entity nor explicitly reserved by stable project design MUST NOT appear only for possible future use.
- Paths internal to a `Submodule`, `Skill`, or another provider-owned entity MUST NOT be modeled by the consuming project's map unless the consuming project owns an explicit specialization for that exact path.
- Removing a provider-owned internal path from the consuming project's map does not remove or weaken the applicable provider contract.
