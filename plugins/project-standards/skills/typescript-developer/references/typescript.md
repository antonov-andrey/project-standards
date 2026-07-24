# TypeScript Contract

- Use strict TypeScript and the runtime, compiler, formatter, linter, package manager, and generated-client versions selected by the project.
- Keep one canonical type for one project-local semantic entity. Normalize untrusted or multi-shape external input at its boundary.
- Generated API clients and generated schema types are canonical for their declared server boundary; handwritten duplicates and field-renaming mapper layers are forbidden.
- Avoid `any`, unsafe assertions, non-null assertions used to hide missing validation, and duplicated derived state.
- Keep async errors observable and preserve the concrete controlling error for the UI or caller.
- Instant values remain RFC 3339 UTC at API and internal boundaries and are localized only for presentation.
- Run the project-required format, lint, typecheck, tests, and build after changes.
