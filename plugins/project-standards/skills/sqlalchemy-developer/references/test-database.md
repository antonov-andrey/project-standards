# SQLAlchemy Test Database Contract

## Test DB Seeding Rules

- Applicability: these rules apply to `_test` DB seeding flows that copy project data for debugging or verification.

- Git-tracked test fixture or seed artifacts are the only stable source for automatic `_test` data population before tests.
- `_test` DB seeding from production MUST copy only the minimal required rows by default.
- Full-table `_test` seeding is forbidden unless explicitly requested.
- `_test` DB seeding MUST use `SQLAlchemy Session Rules` in `references/session-transaction.md`.
- `_test` DB seeding MUST verify referenced-row presence for the target script read scope:
  - for each FK-backed join or ORM relationship that the target script reads, every seeded row that holds the foreign key used by that read MUST keep the referenced row present in `_test`,
  - do not run the target script until that referenced-row check passes.
