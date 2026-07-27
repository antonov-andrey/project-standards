# SQLAlchemy Table Lifecycle Contract

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
