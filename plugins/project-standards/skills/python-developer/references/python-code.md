# Python Code

- `Python code`
  - Meaning: all existing `.py` files in the governed project repository, including `Submodule`s, that are not ignored by `.gitignore`.
  - Repository-wide rules owner: `project-standards:python-developer` is the single provider owner of reusable repository-wide rules for `Python code` in the governed instruction model.

## General Rules

- Use idiomatic, unsurprising Python and the runtime version declared by the project.
- Keep one stable owner for every module, class, function, model, and algorithm.
- Repeated behavior has one shared implementation owner; compatibility-only proxies and future-use knobs are forbidden.
- Choose a class only for stable state, invariants, lifecycle, polymorphism, framework requirements, or a real long-lived boundary; otherwise use a module-level function.
- Keep external dependencies explicit and injected at the runtime owner.
- Normalize external multi-shape input at its boundary into one narrow typed internal contract.
- Import repository-local symbols canonically at module scope; import cycles, dynamic local symbol lookup, fallback imports, and deferred missing-dependency failures are forbidden.
- Use `Path` for internal filesystem contracts and normalize text paths at explicit external boundaries.
- Keep canonical field types, defaults, constraints, and normalization at the field owner; callers do not recast, renormalize, or add fallback defaults.
- Preserve UTC instants according to `project-foundation/references/temporal-data.md`.
- A refactor reaches the final intended state, migrates every in-repository call site, and leaves no compatibility bridge unless the user explicitly requests a staged migration.
- New or renamed owner-controlled names use the stable core concept first and keep one canonical entity name across code, storage, docs, CLI, and other layers.
- Format touched Python code with the project-declared formatter and run direct changed-behavior tests before broader verification.

## Validated Objects

- Detached non-ORM objects that carry stable field-like data across a boundary or stable handoff use the project's canonical strict validated-object foundation.
- Standard construction and assignment validation remain active; bypass construction, hidden pre-coercion, compatibility defaults, and field-mirroring getters or properties are forbidden.
- `None` represents absence only when absence is a real distinct domain value. An optional text label that has canonical empty-string semantics stores `''`.

## File Layout

- Keep imports at module scope in standard-library, third-party, and project-local groups.
- Keep constants, module variables, public functions, and classes in deterministic dependency-aware order.
- Place a private module-level helper immediately before its first owning consumer and keep it only when it owns a real invariant, boundary, reusable algorithm, or substantial behavior.
