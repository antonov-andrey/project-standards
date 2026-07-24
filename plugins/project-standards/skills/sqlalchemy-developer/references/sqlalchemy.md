# SQLAlchemy Contract

- SQLAlchemy use is ORM-first. Use mapped classes, attributes, relationships, and bound expressions when they can express the behavior.
- Runtime values are never interpolated into SQL text. Raw SQL and dynamic identifiers require a proven ORM limitation and bound values.
- One persisted field has one canonical typed ORM contract synchronized with the backing column's type, nullability, and default semantics.
- `None` is used only when absence is a real separate value. Canonical empty text uses `''`.
- Every instant follows `project-foundation/references/temporal-data.md`.
- Project database bootstrap happens before repository logic relies on project tables.
- Sessions are opened through the project's canonical provider, are injected into domain code, and have one explicit lifecycle owner.
- One process uses one primary session by default. Additional sessions exist only for a real separate binding or participant.
- Write flows have explicit transaction ownership. Code receiving a caller-owned session does not open an unapproved nested boundary or sanitize the session with normal-flow rollback, close, or reset.
- Engine, session factory, concurrency, fork, transaction, expiration, and close behavior are traced through the complete call flow before an API migration.
- Schema migrations reach one final steady state without compatibility bridges and are verified against the real pre-migration source state.
