# Submodule Model

- `Submodule`
  - Meaning: a git submodule root treated as a sibling repository entity with its own `Submodule code`, local `tool`, local `test`, `Submodule AGENTS.md`, and other local assets such as data files, images, and text artifacts.
  - Ownership: one `Submodule` owns its full local repository boundary and all entity-local assets inside that root.
- `Submodule code`
  - Meaning: the code entity owned by one `Submodule` for its local runtime and business logic.
  - Membership: it includes product backend code, product frontend code, product deployment configuration, reusable library code, persisted-entity code, script-family code, and submodule entrypoints when those entrypoints are runtime or business wrappers rather than standalone support utilities.
  - Exclusions: it does not include `Submodule AGENTS.md`, local `test`, local `tool`, or other non-code local assets of that `Submodule`.
  - Rule composition: it follows the shared `Code` layer, capability skills selected for the owning `Submodule` through `External Standard Reference Rules`, and the applicable `Submodule AGENTS.md` chain within its declared boundary.

## Python Portability Contract

- Applicability: these rules apply to `Submodule code` implemented in Python.
- `Submodule code` implemented in Python MUST NOT hardcode project-specific DB identifiers, path identifiers, or project identifiers.
- The portability delta for a `Submodule`-owned `Python script` is that it MUST launch from the repository root by direct relative path under the `Submodule` root, and it MUST also launch from the `Submodule` root by the same direct script path, with an optional `./` prefix allowed there too.

## Verification Ownership Contract

- Reusable runtime behavior of one `Submodule` MUST be tested under that `Submodule`'s local `test` root and remain runnable both standalone and through a consumer's explicit shared pytest plugin.
- A `Submodule` whose stable host contract has a mechanically enforceable subset MAY expose one root `project-standard-check.toml` manifest and owner-local checker implementation under its `tool/**`; that manifest and checker follow root `DESIGN.md`, section `Манифест И Протокол Процесса`.
- One submodule host-conformance checker receives the consumer project root through the shared checker protocol, validates only the mechanically enforceable subset of the submodule's own `DESIGN.md` host contract, and remains read-only.
- Consumer repositories MUST NOT copy one submodule-owned runtime behavior test or host-conformance checker into their own `test/code/**`.
