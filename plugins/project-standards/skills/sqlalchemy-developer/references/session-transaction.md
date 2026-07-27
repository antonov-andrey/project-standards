# SQLAlchemy Session And Transaction Contract

## Production Database Rules

- Do not perform production DB writes unless the user explicitly requests them.

## SQLAlchemy Session Rules

- Applicability: these rules apply whenever runtime flows or `_test` flows open project SQLAlchemy sessions.

### Bootstrap Contract

- The governed project's canonical database bootstrap is the only public project-table bootstrap helper.
- When the governed project declares the standard `model_sqlalchemy` provider, `model_sqlalchemy.database.project_database_ensure(use_test=...)` is that canonical public project-table bootstrap helper.
- Project-table bootstrap MUST happen before repository logic relies on project tables.
- `Main project code` runtime, domain, and business flows MUST NOT perform manual project-table or project-schema readiness checks such as `inspect(...).has_table(...)`, owner-local `*_table_ensure()` helpers, or equivalent alternative bootstrap logic.
- When `Main project code` already receives a caller-owned or injected SQLAlchemy session, that session MUST already be project-table ready before the code uses it.

### Session Ownership And Lifecycle

- The governed project's canonical project session provider is the only public project session-opening helper.
- When the governed project declares the standard `model_sqlalchemy` provider, `model_sqlalchemy.database.project_session_get(use_test=...)` is that canonical public project session-opening helper.
- Project SQLAlchemy sessions MUST follow the selected shared SQLAlchemy configuration provider's session-opening contract.
- When the governed project declares the standard `config_sqlalchemy` provider, project SQLAlchemy sessions MUST follow the `config_sqlalchemy` session-opening contract.
- For PostgreSQL-backed project databases, production versus `_test` database selection MUST happen through the database name passed to the canonical session provider; SQLAlchemy `table.schema` MUST NOT be used as the production/test selector.
- One process MUST use one primary SQLAlchemy session by default.
- Additional sessions are allowed only when the runtime requires separate DB bindings or another separately owned DB participant required by the real runtime contract; they MUST NOT be created only to isolate or sanitize transaction state.
- Session creation inside domain or business classes is forbidden.
- Hidden session helpers and session singletons are forbidden.
- Caller-owned or injected SQLAlchemy sessions MUST be treated as valid boundary objects.
- `Main project code` MUST NOT derive physical database names from SQLAlchemy session bindings or engine URLs; use stable project database keys instead.
- Runtime code MUST NOT use `commit()`, `rollback()`, `reset`, `expire`, `close`, fresh sessions, fresh connections, or similar operations only to isolate the next workflow step or to sanitize caller-owned or injected session state.
- Session cleanup beyond explicit failure handling stays with the session owner.

### Transaction Boundary Contract

- Write flows MUST use explicit transaction boundaries.
- A write-flow transaction boundary is explicit when the governing runtime contract makes the bounded write phase and its completion owner explicit, and that boundary closes through normal transaction-context exit or explicit `commit()` at the documented owner.
- The absence of `with session.begin()` is not by itself a defect.
- Code that receives a caller-owned or injected SQLAlchemy session MUST NOT open another transaction boundary on that session; that boundary is owned only by the documented session owner and MAY be split further only when a narrower owner rule explicitly requires batching, retry isolation, or another correctness constraint.
- `rollback()` is allowed only when the current transaction owner is actually aborting the current transaction because of failure or another explicit abort condition; it MUST NOT appear in normal-flow transaction choreography.
- Additional transaction boundaries are allowed only when batching, retry isolation, or another correctness constraint requires them.
- When extra boundaries are required, the owning code or governing contract when contract-relevant MUST make that reason explicit.
- Read-only explicit transaction boundaries are allowed only when the runtime or DB contract requires them and MUST NOT be introduced only to compensate for hidden session-state handling problems.
