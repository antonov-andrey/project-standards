# Submodule Model

- `Submodule`
  - Meaning: a git submodule root treated as a sibling repository entity with its own `Submodule code`, local `tool`, local `test`, `Submodule AGENTS.md`, and other local assets such as data files, images, and text artifacts.
  - Ownership: one `Submodule` owns its full local repository boundary and all entity-local assets inside that root.
- `Submodule code`
  - Meaning: the code entity owned by one `Submodule` for its local runtime and business logic.
  - Membership: it includes product backend code, product frontend code, product deployment configuration, reusable library code, persisted-entity code, script-family code, and submodule entrypoints when those entrypoints are runtime or business wrappers rather than standalone support utilities.
  - Exclusions: it does not include `Submodule AGENTS.md`, local `test`, local `tool`, or other non-code local assets of that `Submodule`.
  - Rule composition: it follows the shared `Code` layer, capability skills selected for the owning `Submodule` through `External Standard Reference Rules`, and the applicable `Submodule AGENTS.md` chain within its declared boundary.
