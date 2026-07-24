# model_sqlalchemy

- `model_sqlalchemy`
  - Meaning: the canonical persisted-entity owner root family.
  - Subset status: `model_sqlalchemy` is a specialized subset of `Main project code` for persisted-entity ownership.
  - Root owner: `model_sqlalchemy/**` in the root repository.
  - Submodule portability: inside a `Submodule`, use the same `model_sqlalchemy/**` owner root relative to the `Submodule` root.
  - Exclusivity: do not create a parallel canonical owner for an entity already owned by `model_sqlalchemy`.
  - Allowed contents: ORM table models; persisted-entity invariants, alternative constructors, and behavior intrinsic to one entity whose implementation operates only on that row's mapped attributes or mapped relationships; project database registry; and DB-specific function or view DDL definitions.
  - Forbidden contents: backend API validation, request or response schemas, UI behavior, product workflow or orchestration logic, behavior owned by a cross-entity service or external integration, and non-DB helper libraries.
  - Repository-wide rules owner: `project-standards:sqlalchemy-developer`.
