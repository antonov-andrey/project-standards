# Project Standards

Codex marketplace repository for a complete reusable engineering-standard catalog whose skills apply independently by their provider-owned triggers.

```bash
codex plugin marketplace add antonov-andrey/project-standards --ref main
codex plugin add project-standards@project-standards
```

Validate the provider from the checkout root:

```bash
python ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/project-standards
pytest -q
```
