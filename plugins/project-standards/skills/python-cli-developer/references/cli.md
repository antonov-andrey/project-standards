# Python CLI Contract

- Every intentionally executable script implements `--help` through its normal import, parser construction, and argument-parsing path.
- A nested script that needs repository-local imports establishes the required import path before those imports.
- Root product entrypoints are thin wrappers; bootstrap, dependency wiring, workflow invocation, and final reporting remain contiguous at the real top-level run owner.
- CLI type and numeric range validation happen at parse time. Runtime clamping and cast-only configuration builders are forbidden.
- Parser destination names match validated configuration fields unless an external contract requires one explicit mapping.
- Environment binding uses the canonical parser provider selected by the project.
- A secret is declared explicitly and remains environment-only. It is absent from argv, help values, errors, and ordinary logs.
- Ordinary environment-backed values retain their effective deployment defaults in help.
- Direct verification runs the real entrypoint, its `--help`, and the affected safe runtime path. A test-mode contract selected by the project must route every owned database binding consistently.
