# Script Catalog Rules

- `docs/script_catalog.md` is the canonical operational catalog for root product entrypoint scripts when a project has such a catalog.
- Keep the catalog limited to script purpose, pipeline position, and run or test differences from general project script principles.
- List root product entrypoint scripts alphabetically in the catalog section.
- Update the catalog when a change adds, removes, renames, or materially reclassifies one root entrypoint or one script-family owner package.
- Update it when a change modifies non-default run behavior, test semantics, production-bound safety, supported stage selection, or safe targeted-run selection.
- Do not make the catalog a second owner for implementation details, internal data structures, or interface contracts.
