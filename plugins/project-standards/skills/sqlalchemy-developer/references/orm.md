# SQLAlchemy ORM Contract

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

### Reusable Project ORM Field And Index Contract

- A governed project MAY define one reusable standard field family through public factories named
  `model_<field_name>_column_get` under its shared `lib/model_sqlalchemy/**` owner.
- When that family exists:
  - every root `model_sqlalchemy/**` row that declares `<field_name>` MUST use the matching
    `model_<field_name>_column_get` factory;
  - root row models MUST inherit the project shared ORM base under `lib/model_sqlalchemy/**`;
  - standard table-argument generation belongs to that shared base and MUST NOT be called manually by individual row
    models;
  - a row-local custom `Index(...)` MUST NOT contain only fields from the standard field family;
  - one mutable row with `t_create`, `t_update`, and `is_deleted` MUST receive its synchronized creation timestamps
    from the shared row construction flow instead of enabling an independent `t_create` default factory.
- When the standard family contains `zitadel_user_id`, shared index generation MUST provide
  `ix_<table_name>_zitadel_user_id` for a row without `is_deleted`, or
  `ix_<table_name>_zitadel_user_id_is_deleted` for a row with `is_deleted`; the latter replaces the redundant
  owner-only index.
- When the standard family contains `zitadel_user_id`, `name`, and `is_deleted`, enabled standard name uniqueness
  MUST use one non-partial unique index `ux_<table_name>_zitadel_user_id_name` over
  `(zitadel_user_id, name)`, including soft-deleted rows.
- Product API managed-field declarations, when present, MUST be a strict subset of the standard field family and
  MUST NOT classify `name` or `description` as framework-managed fields.
