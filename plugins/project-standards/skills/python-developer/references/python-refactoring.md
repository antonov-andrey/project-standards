# Python Refactoring

## Applicability

These rules apply to code refactors and code renames governed by the Python code contract.

## Refactor Steady-State Contract

- Refactors and renames MUST:
  - leave the changed code in the final intended steady state at handoff,
  - migrate all in-repository call sites and dependent code in the same coordinated change,
  - include any directly related fallout fixes needed to keep dependent code, tests, instructions, documentation artifacts, and required verification passing, even when they land outside the initially named files or directories, and do not ask for separate scope approval solely because of that wider landing zone,
  - leave changed in-scope files on current canonical structure and contracts.

## Refactor Target Derivation

- During refactor planning, documentation updates for refactors, and refactor implementation, existing code MUST be used only as evidence of the current behavior, dependencies, and task boundaries; target naming, target owner boundaries, and target structure MUST be derived from the applicable instructions and the required end state instead of being copied from legacy names, legacy layering, or legacy file layout.
- Refactors and renames in non-`Legacy` code MUST apply the same project-local naming-analogy rules required for new non-`Legacy` code by `references/python-naming.md`; copying legacy nouns, legacy helper categories, or legacy phase names into the target is forbidden when a nearer non-`Legacy` analogy already exists.
- Refactors in `Main project code` MUST move the code toward the same structure required for new `Main project code` by `Class Necessity Contract`; preserving helper-heavy legacy decomposition or class shells with no real object role as the target is forbidden.

## Refactor Bridge-State Ban

- Refactors and renames MUST NOT leave intermediate compatibility states, compatibility layers, preserved legacy call shapes, transition-only artifacts, or other refactor-only bridge structures unless the user explicitly requests a coordinated multi-step migration.
- Examples of forbidden refactor-only bridge structures include convenience wrappers, preserved-call-shape helpers, intermediate objects introduced only to make the refactor easier, thin profile wrappers that only prefill constructor arguments, and generic mechanics left in host code after the real owner became clear.
- Refactor and repair work MUST NOT weaken one already approved type or domain contract only to bypass import cycles, forward-reference rebuild friction, framework limitations, or other local implementation obstacles.
- Replacing one concrete approved carrier with a broader fallback carrier such as one base class, one generic `Protocol`, `object`, or one generic mapping shape is forbidden when that replacement exists only to make the change compile, import, or pass tests.
- When current dependency direction or module placement makes one approved contract awkward to implement, code MUST fix that dependency direction or owner placement instead of weakening the contract.
- If one real fix would require changing the approved contract, stop and report that blocker explicitly; do not land one temporary or pragmatic contract-widening workaround.
