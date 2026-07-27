---
name: sqlalchemy-developer
description: Develop SQLAlchemy models, fields, engines, sessions, transactions, bootstrap, migrations, lifecycle, or test databases.
---

# SQLAlchemy Developer

Read `references/model-sqlalchemy.md` and `references/orm.md` when ORM ownership, models, mapped fields, relationships, or queries are in scope.

Read `references/session-transaction.md` when engines, bootstrap, sessions, production writes, or transaction ownership are in scope. Read `references/migration.md` for schema migrations or schema-affecting renames. Read `references/table-lifecycle.md` when selecting or changing a table lifecycle. Read `references/test-database.md` for `_test` DB seeding.

Apply `project-foundation/references/temporal-data.md` to every temporal field.

Use ORM-first behavior, explicit session and transaction ownership, canonical provider APIs, and final-state migrations. Analyze every engine and session call site before refactoring; mechanical replacement is forbidden.

For a write flow, name the single orchestration or session owner that closes or commits the transaction; lower-level helpers receiving its session must not commit.
