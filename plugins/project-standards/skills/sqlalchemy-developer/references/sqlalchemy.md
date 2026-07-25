# SQLAlchemy And Database Contract

## Production Database Rules

- Do not perform production DB writes unless the user explicitly requests them.

## Database Schema Migration Rules

- Applicability: these rules apply to project schema migrations and to schema-affecting table or column renames.

### Applicability And Steady-State

- Database schema migrations MUST leave both the changed code and the changed DB schema in the final intended steady state at handoff.
- One canonical migration case is required only when the current change set still needs to apply a schema transition to a not-yet-migrated DB state.
- When the final target schema is already present on both production and `_test`, do not add, restore, or require a retroactive migration case solely to backfill that already-applied schema history.
- If the production schema is already at the target state and `_test` has obsolete table shapes, drop the affected `_test` tables and let `project_database_ensure(use_test=True)` recreate them instead of creating migration-only `_test` repair cases.

### Migration Bridge-State Ban

- Database schema migrations MUST NOT leave intermediate compatibility states, compatibility layers, mirrored schema objects, transition-only artifacts, or other migration-only bridge structures in code or DB unless the user explicitly requests a coordinated multi-step migration.

### Canonical Migration Case Layout

- `tool/migrate_db/` is the canonical root for database schema migration cases.
- One database schema migration case is one timestamped child directory under `tool/migrate_db/`, named `YYYYMMDDHHmmSS`.
- That child directory MUST contain `tool/migrate_db/<migration_case>/migrate_db.py`.
- `tool/migrate_db/<migration_case>/migrate_db.py` MUST support `--test`.
- `tool/migrate_db/<migration_case>/migrate_db.py --test` MUST be idempotent on a fresh `_test` DB prepared in the required pre-migration source state.

### Canonical Migration Verification Command

- `python tool/migrate_db_test.py YYYYMMDDHHmmSS` is the `Canonical migration-verification command`.
- `Canonical migration-verification command` MUST:
  - recreate `_test` from the current production schema state,
  - treat the current production tables as the only canonical pre-migration source state and MUST NOT use the current `_test` tables as that source state or as a fallback baseline,
  - load `tool/migrate_db/<migration_case>/{database_name}.{table_name}.source.jsonl`,
  - run `tool/migrate_db/<migration_case>/migrate_db.py --test`,
  - validate the migrated `_test` schema strictly through `model_sqlalchemy.database.project_database_ensure(...)` and `model_sqlalchemy.database.project_session_get(...)`,
  - validate `tool/migrate_db/<migration_case>/{database_name}.{table_name}.target.jsonl` for every table that declares migration data artifacts.
- Migration MUST be verified using `Canonical migration-verification command` before any production migration or implementation handoff.

### Migration Data Artifact Contract

- `tool/migrate_db/<migration_case>/{database_name}.{table_name}.source.jsonl` and `tool/migrate_db/<migration_case>/{database_name}.{table_name}.target.jsonl` are required only for tables whose stored data changes non-trivially during the migration.
- If one of `tool/migrate_db/<migration_case>/{database_name}.{table_name}.source.jsonl` or `tool/migrate_db/<migration_case>/{database_name}.{table_name}.target.jsonl` exists for a table, the other MUST exist too.
- Data validation against `tool/migrate_db/<migration_case>/{database_name}.{table_name}.target.jsonl` MUST compare unordered row sets.

### Migration Runtime Output Contract

- `tool/migrate_db/<migration_case>/migrate_db.py` MUST print one line `MIGRATED_TABLE <database_name>.<table_name>` after each migrated table.
- Migration scripts MUST validate the expected source database state before applying schema or data changes and MUST fail on already-applied or otherwise unexpected database states.
- Applied migration cases are transient: after one migration case has been successfully applied to every target database required by the current release, delete its `tool/migrate_db/<migration_case>/` directory instead of preserving historical migration cases in the repository.

## ORM Ownership

- Generic ORM models and generic project database-bootstrap artifacts MUST be owned by `model_sqlalchemy`.
- Reusable persistence that is generic to one `Submodule` MUST be owned by that `Submodule`.
- Boundary-local DTOs or schemas are allowed only when they remain local to one boundary and do not become a second canonical model for that persisted entity.
- Product behavior, backend API validation, request and response schemas, and workflow rules MUST NOT live in `model_sqlalchemy`; they belong to their product, backend API, workflow, or boundary owner.

## ORM Rules

- SQLAlchemy usage is ORM-first.
- Use ORM constructs when behavior is expressible with mapped ORM classes, mapped ORM attributes, or mapped ORM relationships.
- Query, read, and write paths MUST use mapped ORM classes, mapped attributes, and ORM operations for normal cases.
- Raw SQL MUST NOT be used when equivalent behavior is expressible with SQLAlchemy ORM objects, attributes, or relationships.
- ORM-bypass table or column access via `__table__`, `.c`, or direct identifier plumbing MUST NOT be used when mapped ORM objects or attributes can express the same logic.
- Query joins SHOULD use relationship attributes instead of explicit `ON` clauses when relationships exist.
- SQLAlchemy ORM expressions are the default SQL-injection defense for product data values.
- Runtime data values used in SQLAlchemy queries MUST be passed through ORM expressions, SQLAlchemy Core expressions, or explicit bound parameters.
- `text()` and explicit DB, table, or column identifiers MAY be used only when ORM cannot solve the task cleanly or correctly.
- Raw SQL text MUST NOT be built with f-strings, string concatenation, `.format(...)`, percent-formatting, or other runtime-data interpolation.
- When raw SQL text is objectively required, every runtime data value in that SQL MUST be supplied through SQLAlchemy bound parameters instead of being rendered into the SQL string.
- `ForeignKey` constraints MUST NOT be introduced in governed ORM models.
- Table relationships used by repository ORM code MUST be expressed either as reusable relationship declarations in `model_sqlalchemy` or explicitly in the query itself for custom cases.
- ORM classes that represent one persisted database row under `model_sqlalchemy/**` MUST inherit from `OrmBase`.
- ORM classes that represent one persisted database row MUST expose only instance methods plus optional alternative constructors.
- On ORM classes that represent one persisted database row, `@staticmethod` is forbidden, and `@classmethod` is forbidden except for alternative constructors.
- An alternative constructor on an ORM class that represents one persisted database row MUST be a `@classmethod` that builds and returns one instance of that same ORM model.
- If an ORM class that represents one persisted database row needs an alternative constructor, that alternative constructor MUST be implemented on that same ORM model instead of as an external helper.
- Instance methods on ORM classes that represent one persisted database row MUST operate only on that concrete row instance and its own mapped attributes or mapped relationships.
- `OrmBase` runtime semantics MUST stay as close as possible to `BaseModelStrict`: strict constructor validation plus direct field reassignment validation, without extra mutation-wrapper layers or load/refresh instrumentation.
- ORM classes that represent one persisted database row MUST expose mapped field state directly through canonical mapped attributes instead of getter/setter wrappers, field-mirroring `property` wrappers, or equivalent accessor methods such as `*_get()`, `get_*()`, `*_set()`, or `set_*()`.
- ORM rows loaded from DB MUST be treated as already-clean objects; post-load validation, post-load normalization, and post-load cleanup of mapped fields are forbidden.
- `OrmBase.payload_get(**kwargs)` is the canonical field-dump persistence method for one ORM row.
- ORM field declarations for one persisted database row MUST use typed SQLAlchemy `Mapped[...]` annotations; `Mapped[...]` is the only owner of Python field type for one `OrmBase` field contract.
- `mapped_column(...)` is the only owner of DB and column semantics for one `OrmBase` field contract, including SQL type, `nullable`, scalar `default`, `server_default`, `insert_default`, indexes, foreign keys, primary-key semantics, and other column-level schema details; legacy `Column(...)`-style field declarations are forbidden.
- When one `OrmBase` field contract uses one owner-controlled `list[...]`, `dict[...]`, or `set[...]` carrier, the backing DB column name MUST use the same stable suffix as the mapped field name: `..._list`, `..._map`, or `..._set`.
- `info["validated_object"]` on one `OrmBase` field is allowed only for `normalizer` and `default_factory`.
- `info["validated_object"]["python_type"]` and `info["validated_object"]["validate"]` are forbidden.
- Nullability for one `OrmBase` field contract MUST NOT be declared anywhere except `mapped_column(nullable=...)`.
- ORM field `default` is allowed only for scalar literal constructor defaults.
- ORM field `default_factory` is allowed only for no-arg-invocable pure Python constructor factories.
- Callable ORM field `default` is forbidden; Python-side callable constructor defaults MUST use `default_factory` instead.
- `insert_default` is allowed only for insert-time generation semantics.
- `insert_default` MUST NOT be used as a replacement for constructor defaults of canonical fields.
- `server_default` belongs only to DB schema contract and MUST NOT be treated as the source of one clean canonical field value on a new detached Python object before persistence round-trip.
- For one persisted ORM field, the mapped field contract and the backing DB column definition MUST stay synchronized by type, `NULL` / `NOT NULL`, and default semantics as far as that behavior is expressible by the column definition itself.
- ORM field validation MUST NOT accept values that the real backing DB column definition forbids.
- Code-only defaults and DB-only defaults for one persisted ORM field are forbidden unless they express the same final semantics explicitly and equivalently across the ORM field contract and the backing DB column definition.
- Python-side ORM validation MAY be stricter than the backing DB column definition only for field semantics that are not technically expressible by the DB column definition itself without workaround layers.
- Triggers, companion schema objects, generated helper structures, or other non-column workaround validation layers MUST NOT be introduced only to imitate stricter column-level validation than the DB column definition can express directly.
- Column order in ORM model definitions MUST remain alphabetical.
- `None` is used only when absence is a real separate value. Canonical empty text uses `''`.

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

## Table Lifecycle Ownership

- Every governed non-external product ORM table MUST select exactly one applicable shared lifecycle profile unless a narrower stable owner defines another complete lifecycle.
- Externally owned service tables are outside consumer product lifecycle profiles.
- A narrower stable domain contract MAY select another complete lifecycle. Overlapping column names alone do not change profile semantics.
- Existing unclassified or `Legacy` tables are not automatically migrated, and the shared profiles are not retrofit requirements.
- Every lifecycle timestamp remains subject to `project-foundation/references/temporal-data.md` and preserves the precision declared by its selected profile or narrower stable owner.

### Mutable Product-State Lifecycle

- This profile applies to mutable Product state whose current row is authoritative.
- The profile uses `t_create`, `t_update`, and `is_deleted`.
- Creation sets `t_create` and `t_update` to one exact current UTC timestamp with microsecond precision.
- Update sets `t_update` to the exact current UTC timestamp with microsecond precision.
- Soft delete sets `is_deleted=true` and sets `t_update` to the exact current UTC timestamp with microsecond precision.
- Ordinary readers exclude rows with `is_deleted=true`.
- Runtime domain operations MUST NOT physically delete rows under this profile.

### Append-Only Log Lifecycle

- This profile applies to Product log, event, audit, and history rows.
- The profile requires `t_create` and MUST NOT use `t_update` or `is_deleted` unless a narrower stable owner defines a real exception.
- Creation sets `t_create` to the exact current UTC timestamp with microsecond precision.
- Runtime domain operations MUST NOT update, soft-delete, or physically delete rows under this profile.
- Cleanup is allowed only through retention, rotation, partition drop, migration, or maintenance.

### Refreshable Snapshot Lifecycle

- This profile applies when a table is refreshed from one source over one complete lifecycle scope.
- The profile uses `t_create`, `t_update`, and `is_deleted`.
- `t_update` means refreshed-at and changes for every row refreshed or otherwise modified in the current scope, including unchanged payloads and rows marked stale.
- The default complete lifecycle scope is one unfiltered run. A narrower stable owner MAY define one complete partition as the lifecycle scope.
- Stale finalization runs only for a complete lifecycle scope and MUST be skipped for filters narrower than that scope.
- Stale finalization soft-deletes stale rows by setting `is_deleted=true`, and ordinary readers exclude rows with `is_deleted=true`.
- Lifecycle timestamps under this profile use UTC without microseconds.

## Test DB Seeding Rules

- Applicability: these rules apply to `_test` DB seeding flows that copy project data for debugging or verification.

- `_test` DB seeding from production MUST copy only the minimal required rows by default.
- Full-table `_test` seeding is forbidden unless explicitly requested.
- `_test` DB seeding MUST use `SQLAlchemy Session Rules`.
- `_test` DB seeding MUST verify referenced-row presence for the target script read scope:
  - for each FK-backed join or ORM relationship that the target script reads, every seeded row that holds the foreign key used by that read MUST keep the referenced row present in `_test`,
  - do not run the target script until that referenced-row check passes.
