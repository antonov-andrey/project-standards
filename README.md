# Project Standards

Codex marketplace repository for reusable, independently selectable engineering standards.

```bash
codex plugin marketplace add antonov-andrey/project-standards --ref main
codex plugin add project-standards@project-standards
```

Validate the provider from the checkout root:

```bash
python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/project-standards
pytest -q
```
