# Codex Process State

## Standard Home

One Codex worker runs as one operating-system user with that user's standard `$HOME/.codex` state. `HOME` MUST equal the home recorded for the current operating-system user and `CODEX_HOME` MUST be absent.

Project code, workflows, evaluation harnesses, and task launchers MUST NOT create, copy, mount, pass, substitute, or delete an alternate Codex home. They MUST NOT copy authentication into task-owned state, create task-specific Codex profiles, replace `HOME`, pass `--ephemeral`, disable history persistence, or otherwise bypass the standard home.

Server or worker bootstrap owns authentication, configuration, installed plugins, caches, session state, and history in the standard home. A worker that requires an incompatible plugin revision uses a separately provisioned operating-system user or worker. Repository worktrees and the declared sandbox own source and filesystem isolation; Codex home substitution does not.

## Waiting And Resume

The outer harness owns native process completion and cancellation. Project code and workflows MUST NOT add polling loops or fixed timeouts around a Codex process unless a separate product contract defines a result-semantic deadline.

Resume eligibility is semantic. It binds the task inputs, owned source revisions, required capabilities, and result-affecting environment or release inputs. Exact Codex binary version and unrelated global worker state MUST NOT become resume gates. A changed environment or release value belongs in resume identity only when the owning contract establishes that it can change the result.

## Usage Telemetry

Record token or usage telemetry only when the invoked Codex surface exposes the exact value directly. Preserve that exact value and its unit or omit the field. Estimates and values inferred from conversation text, session logs, or output size are forbidden.
