# SQLAlchemy Migration Contract

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
