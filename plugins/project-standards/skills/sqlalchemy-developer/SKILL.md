---
name: sqlalchemy-developer
description: Use when changing SQLAlchemy models, persisted fields, engines, sessions, transactions, database bootstrap, migrations, table lifecycle, or test database behavior.
---

# SQLAlchemy Developer

Read `references/model-sqlalchemy.md` and `references/sqlalchemy.md` completely. Apply `project-foundation/references/temporal-data.md` to every temporal field.

Use ORM-first behavior, explicit session and transaction ownership, canonical provider APIs, and final-state migrations. Analyze every engine and session call site before refactoring; mechanical replacement is forbidden.
