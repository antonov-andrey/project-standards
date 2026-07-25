# Python Code

- `Python code`
  - Meaning: all existing `.py` files in the governed project repository, including `Submodule`s, that are not ignored by `.gitignore`.
  - Repository-wide rules owner: `project-standards:python-developer` is the single provider owner of reusable repository-wide rules for `Python code` in the governed instruction model.

The complete reusable implementation contract is split by concern without changing its combined applicability:

- `references/python-core.md` owns formatting, signatures, imports, validated objects, class design, runtime ownership, and file layout;
- `references/python-refactoring.md` owns final-state refactor and rename behavior;
- `references/python-naming.md` owns canonical naming and cross-layer field identity;
- `references/python-ownership.md` owns visibility, dead code, and owner placement outside `Submodule` code.

Every changed non-`Legacy` Python scope applies all four references together. More specific capability skills add their boundary contracts; they do not replace these references. Preserve UTC instants according to `project-foundation/references/temporal-data.md`.
