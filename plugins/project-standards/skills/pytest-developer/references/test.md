# Pytest Contract

## Test Implementation Contract

- Tests MUST be written as `pytest` tests.
- Root `pytest` is the canonical repository suite and MUST auto-discover owner-local `test` roots through the explicitly enabled shared pytest plugin.
- Shared owner-local suite discovery MUST be provided by the explicit `project-standards` pytest plugin. Consumer repositories MUST enable that plugin explicitly through pytest configuration and MUST NOT copy its discovery implementation into root `conftest.py` or `test/lib/**`.
- A root `conftest.py` MAY remain only for real consumer-local fixtures, hooks, or marker registration not owned by the shared plugin.
- The shared plugin MUST discover the root `test`, every tracked project-local `Skill/test`, and direct-submodule owner-local `test` roots, preserve standalone Skill and Submodule execution and explicit pytest selection, exclude tests from the installed provider distribution, ignored worktrees, virtual environments, caches, build outputs, `.spec`, and unrelated nested repositories, and report deterministic discovery.
- The shared plugin MUST NOT own Product fixtures, project markers, test data, or consumer-specific collection policy.
- Tests under the root repository MUST be runnable through the root virtualenv pytest entrypoint, including tests that exercise `Submodule` behavior.
- `Submodule` tests MUST remain runnable both when the owning `Submodule` is used standalone and when that `Submodule` is present in the root repository and its tests run through that same root virtualenv pytest entrypoint.

## Test Families And Placement

- Test families:
  - `test/**` is the default owner-local location for behavior tests.
  - `test/integration/**` is for slower or environment-dependent tests and for tests that exercise real external boundaries.
  - `test/code/**` is the optional consumer-local code-contract branch for exact project or Product integration restrictions that have no reusable provider owner.
  - `test/code/**` is separate from the ordinary handoff suite.
  - An independently normative, closed, and completely decidable mechanical rule of one reusable standard MUST be implemented as a checker under its provider skill and MUST NOT be copied into consumer `test/code/**`.
  - An approximate semantic proxy, heuristic signal, selected example list, or false-positive allowlist MUST NOT be implemented as a checker. Such requirements remain semantic even when a script could find some likely violations.
  - Reusable runtime behavior MUST be tested under the runtime owner, including one owning `Submodule`; a consumer `test/code/**` MUST NOT duplicate those behavior tests.
  - One consumer-local `test/code/**` check MUST name and exercise its exact local integration contract and MUST NOT become a hidden owner for reusable policy.
  - General repository policy, semantic intent, and broad prohibitions MUST be stated in the owning non-test contract; executable checks implement only independently normative closed predicates that they decide completely.
  - Tests MUST NOT assert the presence, absence, exact wording, or ordered text fragments of instruction prose as a proxy for instruction synchronization; instruction-artifact tests MAY validate mechanical structure, syntax, references, parser behavior, executable checker behavior, and machine-facing contract identifiers consumed by executable validators, while semantic drift belongs to semantic audit workflows.
- Owner-local placement:
  - root-repository `test` MUST NOT host owner-local tests of one `Skill`,
  - owner-local tests for one `Skill` MUST live under that same entity's local `test`.
  - reusable behavior tests for one `Submodule` MUST live under that same `Submodule`'s local `test`.

## Handoff Suite Contract

- `pytest --ignore=test/code -q` is the ordinary repository handoff suite for code, tests, runtime behavior, and database behavior when no narrower owner defines another ordinary suite.
- Targeted verification and executable standard checks do not replace the ordinary handoff suite.
- `test/code/**` is not part of the ordinary handoff suite and runs only when the task changes that local contract or helper, the user explicitly requests it, or a narrower workflow gate requires it.
- `project-standard-check --project-root <repository-root> --scope changed` is separate from pytest and runs the declared mechanically enforced standards against their exact scopes. Its clean result is mechanical evidence only and never a semantic verdict.
- Provider checker tests verify checker success, finding, critical edge, scope, and diagnostic behavior in the provider repository; they do not scan a consumer repository as their own test fixture.

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
- a changed provider rule that remains eligible for mechanical enforcement MUST add or update the owning provider checker and its owner-local tests,
- changed exact consumer-local code-structure contracts MUST add or update the owning consumer `test/code/**` check when mechanical verification is appropriate.
- Required changed-behavior coverage MUST include:
  - the success path,
  - the primary contract-defining failure path,
  - every critical edge case or branch introduced by the change.
- When one repository test or code-contract checker fails, inspect the failing test implementation itself before changing production code, test expectations, or instructions.
- That inspection MUST include the failing test body, owner-local test helpers, fixtures, and any adjacent docstring or comments that clarify the exact checker scope.
- Test code is the executable verification contract; comments and docstrings may clarify special cases, but they MUST NOT be treated as stronger than the implemented assertion logic.
