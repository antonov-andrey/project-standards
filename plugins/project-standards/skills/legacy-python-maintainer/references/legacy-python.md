# Legacy Python

- `Legacy`
  - Classification: a root directory that belongs to `Python code`, is not classified by the governed structure model, and is not a `Submodule`.
  - Thin-entrypoint extension: if a root `.py` file is a thin entrypoint whose implementation delegates into a `Legacy` root directory, that root `.py` file belongs to the same `Legacy`.
  - Allowed changes: bug fixes, containment, deletion, or an explicit user-requested migration into a modeled non-`Legacy` owner root.
  - Forbidden direction: do not create or extend new long-lived owner roots under `Legacy`.
  - Migration gate: do not move a `Legacy` root into a modeled non-`Legacy` owner root unless the user explicitly requests that migration.
  - Documentation gate: do not create or update repository documentation artifacts for `Legacy` migration unless the user explicitly requests those artifacts or the migration changes `docs/script_catalog.md` scope.
  - Default handling: ongoing work in one `Legacy` root does not by itself authorize migration out of `Legacy`; without an explicit user-requested migration task, keep the change inside that `Legacy` root.
