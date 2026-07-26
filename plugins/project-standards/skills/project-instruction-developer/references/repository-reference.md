# Repository Reference Rules

- Repository-local references MUST use plain root-relative paths such as `plugins/project-standards/skills/project-instruction-developer/test/test_repository_reference_check.py`, `design/backend.md`, or `docs/script_catalog.md`.
- Root-relative means relative to the owning repository boundary.
- Repository-local Markdown links are forbidden, except same-file heading-anchor links inside an explicit table of contents.
- Bare local relative references such as `./<local>.md` or `../<other>.md` are forbidden.
- A `template path` is an owner-local template path such as `plugins/<plugin>/skills/<skill>/template/**`, `plugins/<plugin>/lib/<owner>/template/**`, or an explicitly mapped project-local template owner.
- References from repository-local templates to repository-local instruction artifacts MUST use the consumed instruction artifact path.
- References from other repository-local artifacts to repository-local instruction artifacts MUST use the consumed instruction artifact path.
- External plugin contracts MUST be referenced by plugin name together with their canonical skill name or plugin-relative owner path; consumer-local substitute paths are forbidden.
- Template sources that are not instruction artifacts MUST be referenced by their template paths.
- A reference to a heading-defined owner MUST use the heading's exact literal text in backticks.
- When that owner lives in another repository-local file, the reference MUST also name its root-relative owning file.
- Paraphrased references are forbidden when the literal target heading already exists.
