# Pytest Contract

## Test Implementation Contract

- Tests MUST be written as `pytest` tests.
- Root `pytest` is the canonical repository suite and MUST auto-discover owner-local `test` roots through the repository-root `conftest.py`.
- Tests under the root repository MUST be runnable through the root virtualenv pytest entrypoint, including tests that exercise `Submodule` behavior.
- `Submodule` tests MUST remain runnable both when the owning `Submodule` is used standalone and when that `Submodule` is present in the root repository and its tests run through that same root virtualenv pytest entrypoint.

## Test Families And Placement

- Test families:
  - `test/**` is the default owner-local location for behavior tests.
  - `test/integration/**` is for slower or environment-dependent tests and for tests that exercise real external boundaries.
  - `test/code/**` is the code-contract branch of one owner-local `test`.
  - `test/code/**` is separate from the ordinary handoff suite.
  - Repository-wide code-contract tests for the whole repository, including runtime-mechanical enforcement of shared repository code rules, MUST live under root `test/code/**` and MUST NOT live elsewhere.
  - `test/code/**` MUST contain only concrete automatically testable implementations of repository rules already owned elsewhere in the governed instruction model.
  - General repository policy, semantic intent, and broad prohibitions MUST be stated in the owning non-`test` rule sections; `test/code/**` MUST implement only the mechanically checkable subset of those rules.
  - Tests MUST NOT assert the presence, absence, exact wording, or ordered text fragments of instruction prose as a proxy for instruction synchronization; instruction-artifact tests MAY validate mechanical structure, syntax, references, parser behavior, executable checker behavior, and machine-facing contract identifiers consumed by executable validators, while semantic drift belongs to semantic audit workflows.
- Owner-local placement:
  - root-repository `test` MUST NOT host owner-local tests of one `Skill`,
  - owner-local tests for one `Skill` MUST live under that same entity's local `test`.

## Test Import And Support Artifact Contract

- `Main project` `test` Python import contract:
  - `Main project` `test` MUST NOT import `test` outside `test/lib/**`.
- Test support artifacts:
  - the owner-local pytest `conftest` file MUST contain only shared pytest fixtures, shared pytest hooks, shared pytest marker/config registration, and private helper code used only by that same owner-local pytest `conftest`,
  - shared imported test helper code MUST live under owner-local `test/lib/**`,
  - non-code fixtures and other non-imported support artifacts MAY live under other clearly named owner-local `test` branches such as `test/fixtures/**`.

## Test Quality And Coverage Contract

- Tests MUST NOT verify instruction artifacts by checking exact prose, headings, examples, file presence, path references, or placement rules; instruction artifacts require semantic review instead of executable text assertions.
- do not depend on execution order, shared mutable global state, production services, or wall-clock timing,
- environment-dependent or slower root-repository tests MUST live under `test/integration/**`,
- environment-dependent or slower `Submodule` tests MUST follow the owning `Submodule`'s local pytest layout and slower-test conventions.
- changed behavior MUST add or update behavior tests when those tests are the direct evidence of correctness,
- changed repository policy or repository code-structure contracts MUST add or update code tests under the owning `test/code/**` root.
- Required changed-behavior coverage MUST include:
  - the success path,
  - the primary contract-defining failure path,
  - every critical edge case or branch introduced by the change.
- When one repository test or code-contract checker fails, inspect the failing test implementation itself before changing production code, test expectations, or instructions.
- That inspection MUST include the failing test body, owner-local test helpers, fixtures, and any adjacent docstring or comments that clarify checker scope, approximations, or allowed exceptions.
- Test code is the executable verification contract; comments and docstrings may clarify special cases, but they MUST NOT be treated as stronger than the implemented assertion logic.
