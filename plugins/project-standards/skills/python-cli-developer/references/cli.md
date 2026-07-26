# Python CLI Contract

## Repository Script Artifact And Root Entrypoint Shape

- Utility scripts and other intentionally executable scripts MUST be `Python script`s.
- Repository `.sh` scripts are forbidden.
- Every intentionally executable script MUST implement `--help`.
- Every intentionally executable script MUST launch its `--help` path by direct script command from its owning repository boundary without `PYTHONPATH` or other inline environment-variable assignments.
- The `--help` path of every intentionally executable script MUST use the script's standard startup, import, parser construction, and argument-parsing path.
- An intentionally executable script MUST NOT branch on `--help` or `-h`, disable standard parser help, define a manual help flag, or return early only to make `--help` work while the normal script launch path remains broken.
- A nested intentionally executable script that needs repository-local imports MUST establish the required import path inside the script before repository-local imports.
- Documentation and instruction artifacts MUST show intentionally executable script commands as direct script commands without inline environment-variable assignments.
- Product root entrypoints MUST:
  - be thin wrappers that own only minimal root bootstrap and direct handoff into one script owner,
  - centralize launch orchestration in one shared root-entrypoint helper under the same `script/<workflow_name>/**` slice or under `lib/**` only when multiple entrypoints share that same launch orchestration,
  - use the canonical parser provider selected by the governed project.
- When the governed project declares the standard `config_argparse` provider, `config_argparse` is its canonical parser provider and every Product root entrypoint MUST use the `config_argparse` parsing contract.

## Script CLI Ownership

- A dedicated script CLI module, when present, MUST own only the definition of script-specific CLI arguments and their parse-time validation.
- A dedicated script CLI module MUST NOT own bootstrap, dependency wiring, or execution logic.

## Interactive CLI Prompt Contract

- Interactive stdin prompts in non-test `Python code` MUST use one owner-local prompt boundary instead of direct `input(...)`.
- Product code outside that owner-local prompt boundary MUST NOT import its interactive prompt framework directly.
- Confirmation prompts MUST accept only case-insensitive `y`, `yes`, `n`, and `no`, MUST treat an empty response as the declared default, and MUST reprompt instead of treating unrecognized non-empty input as refusal.

## CLI-To-Config Contract

- Numeric CLI range validation MUST happen at parse time.
- Runtime clamping of parsed CLI values is forbidden.
- When one script runtime uses one `*Config` model as the parsed-CLI boundary, parser `dest` names MUST match that model's field names exactly unless one explicit owner rule or one public external CLI contract requires one transparent mapping.
- When no such exception applies, the top-level config translation MUST construct that model directly from parsed namespace values, for example `Config(**vars(args))`.
- Field-by-field cast-only or rename-only config builders in entrypoint or bootstrap code are forbidden.
- Type parsing and numeric range validation that can happen at parse time MUST stay in the CLI parser.
- Cross-field invariants or object-local normalization that remain after parse time MUST live on the `*Config` model or another canonical owner, not in root bootstrap glue.
- Environment binding uses the canonical parser provider selected by the governed project.
- When the governed project declares the standard `config_argparse` provider, environment binding MUST use `config_argparse`.
- A secret is declared explicitly and remains environment-only. It is absent from argv, help values, errors, and ordinary logs.
- Ordinary environment-backed values retain their effective deployment defaults in help.

## Test-Mode Runtime Contract

- For a root entrypoint that opens project SQLAlchemy sessions and supports `--test`, that `--test` mode MUST follow this contract:
  - it MUST be exposed only through explicit CLI flags and MUST NOT be mirrored through environment variables, config files, or hidden defaulting,
  - when `--test` is enabled, every project DB binding owned by `Main project code` in that run MUST target the corresponding `_test` DB instead of the primary DB,
  - the top-level run flow MUST propagate that test-mode choice consistently into `project_database_ensure(use_test=True)` before project-table use and `project_session_get(use_test=True)` for project session opening,
  - when `--test` is not enabled, the run MUST NOT silently bind to `_test`.
- Repository-wide generic script classifications MUST NOT be used.
- Repository-wide generic minimal-run CLI contracts MUST NOT be used.
- Every root-entrypoint `Python script` that supports `--test` and has non-default run or testing semantics MUST have those differences summarized in `docs/script_catalog.md`.
- `docs/script_catalog.md` script notes MUST stay limited to:
  - `--test` DB-routing differences from the default project rule,
  - production-bound testing policy differences,
  - minimal safe targeted work units or explicit absence of safe partial runs,
  - script-specific selectors or explicit stage selectors,
  - targeted-run safety constraints that are not obvious from the CLI.
- If one calculation or cleanup path requires a broader scope than the targeted work unit, that broader-scope behavior MUST be isolated into a separate explicit stage or command instead of being hidden inside one supposedly targeted run.
- `mcp-debugger` is an approved optional debugging aid for root-entrypoint runs, but it MUST NOT replace `docs/script_catalog.md` when that catalog owns one script-specific run/test exception, direct CLI verification, or DB-safety contract.

## Direct Verification And Coverage Contract

- When the required direct verification command for a root entrypoint uses `_test` DB verification, remediate `_test` schema drift and rerun the same direct entrypoint command instead of skipping verification.
- When the changed behavior belongs to one root-entrypoint flow in `Main project code`, verification MUST include direct root-entrypoint coverage when the current task changes CLI wiring, top-level runtime wiring, DB-routing semantics, external write gating, or one run/test exception documented in `docs/script_catalog.md`.
- When this section requires verification through a direct root-entrypoint command, that verification MUST run through the real root entrypoint instead of helper wrappers, helper modules, or shortened surrogate runners.
- When a root entrypoint supports `--test`, verification MUST use `--test`; direct verification without `--test` is forbidden unless the user explicitly requires it.
- Required changed-behavior coverage for one in-scope root entrypoint in `Main project code` MUST cover:
  - the CLI contract,
  - the top-level run-flow or runtime-wiring contract,
  - when the entrypoint opens project SQLAlchemy sessions and supports `--test`, a runtime-contract test that asserts the `--test` semantics and targeted-run safety semantics owned by this section and by `docs/script_catalog.md` when that catalog documents a script-specific exception.
