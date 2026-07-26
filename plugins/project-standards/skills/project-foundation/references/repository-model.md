# Repository Model

- `Main project`
  - Meaning: the aggregate repository project entity for the whole repository root.
  - Membership: it includes `Main project code`, `Main project AGENTS.md`, `Main project documentation`, root `test`, root `tool`, `Submodule`, every other project-local entity declared by applicable provider or project-local instructions, and other project-local assets such as `.codex/config.toml`, `log/**`, `Legacy`, data files, images, and text artifacts.
  - Aggregate role: `Main project` is the umbrella project term for the full repository and its member entities, not a replacement for the local ownership of those member entities.
- `Main project code`
  - Meaning: the main root-repository code entity for runtime and business logic.
  - Membership: it includes product backend code, product frontend code, product deployment configuration, reusable library code, persisted-entity code, script-family code, and root entrypoints when those entrypoints are runtime or business wrappers rather than standalone support utilities.
  - Exclusions: it does not include `Main project AGENTS.md`, `Main project documentation`, `Skill`, `Submodule`, `test`, `tool`, or `Legacy`, including thin root Python entrypoints whose implementation owner is `Legacy`.
  - Rule composition: it follows the shared `Code` layer, conditionally applicable capability skills bound through `External Standard Reference Rules`, and explicitly authorized project-local specializations within their declared scope.
  - Import boundary: `Main project code` may import only from `Main project code` or `Submodule code`; it MUST NOT import `Python script`, `test`, or `tool`.
- `Self-contained`
  - Meaning: the entity owns its own private files and local assets within its own boundary.
  - Duplication boundary: duplication of code, instructions, tooling, tests, templates, or other owned assets across `Self-contained` entities is forbidden.
  - Shared-owner rule: when multiple `Self-contained` entities need the same long-lived asset or contract, promote it to one canonical owner instead of cloning it across entities.
- `log`
  - Meaning: the runtime log root family.
  - Root owner: `log/**` in the root repository.
  - Centralization rule: `Submodule` runs executed through the project centralize logs there.
  - Boundary: standalone `Submodule` logging belongs to the standalone `Submodule` contract.
- `Code`
  - Meaning: the shared code-rule layer composed from every conditionally applicable code capability skill bound through `External Standard Reference Rules`.
  - Scope relation: `Code` is the common rule layer beneath owner-specific specializations such as `Main project code`, `Submodule code`, `test`, and `tool`; it does not replace the local ownership of those entities.
  - Ownership: each applicable capability skill remains the single owner of its contributed rule slice; `Code` does not create a second monolithic rule owner or consumer-local copy.
- `test`
  - Meaning: verification code for the `Main project` or for one explicitly declared `Self-contained` owner within it, including a `Submodule` or `Skill`.
  - Role: a support entity, not a business owner.
  - Production-boundary rule: `test` must not become the only owner of production algorithms or behavior.
  - Owner-local placement and scope: `test` uses the canonical placement declared by the owning entity's applicable testing capability and project-local structure contract, and owns verification of that entity, its local support slices, and its owned integration contracts.
  - Rule composition: it follows the shared `Code` layer, conditionally applicable testing capability skills bound through `External Standard Reference Rules`, and explicitly authorized project-local specializations within their declared scope.
- `tool`
  - Meaning: support and control code for the `Main project` or for one explicitly declared `Self-contained` owner within it, including a `Submodule` or `Skill`.
  - Role: a support entity, not a business owner.
  - Output contract: `tool` output, logging, and help text must be English unless a local owner explicitly says otherwise.
  - Owner-local placement: `tool` uses the canonical local tool root declared by its owning entity; shared helper code for that tool root lives under its local `tool/lib/**` branch.
  - Rule composition: it follows the shared `Code` layer, conditionally applicable tool capability skills bound through `External Standard Reference Rules`, and explicitly authorized project-local specializations within their declared scope.

## Tool Utility Ownership Contract

- A second owner-local caller for the same `tool` task MUST trigger extraction of that task into one shared implementation module under that same owner-local `tool/lib/<module>.py`; do not keep the duplicated logic inline in entrypoints or command sequences.
- If two or more `tool` entrypoints in one owner-local `tool` scope perform the same task, each of those entrypoints MUST delegate to that one shared implementation module.
- That shared owner-local `tool/lib/<module>.py` module MUST group utilities for one clearly defined tool task or one coherent tool domain. It MUST NOT become a grab-bag of unrelated helper functions.
- If an owner-local `tool` utility already exists for one action, that utility MUST be used instead of an ad-hoc command sequence.
- Root-repository `tool` MUST NOT host owner-local `tool` utilities of one `Skill`; those utilities MUST stay under the owning entity's local `tool`.
- `tool` MUST NOT import `Python script`.

## Executable Automation Contract

- Every non-ignored project-local path whose name ends in `.sh` is forbidden.
- Standalone non-ignored project-local executable automation MUST NOT be implemented in a shell language. When one standalone script is required, it MUST be a `Python script` governed by `project-standards:python-cli-developer`.
- Executable shell-language code MAY exist only as boundary-local command text inside one externally owned configuration or runtime command field. It MUST stay limited to the minimum adaptation required by that boundary and MUST NOT own reusable project automation or project policy.
