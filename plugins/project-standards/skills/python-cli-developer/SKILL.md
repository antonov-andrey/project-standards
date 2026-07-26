---
name: python-cli-developer
description: Use when adding or changing an executable Python script, replacing shell automation with Python, changing a CLI parser, environment-backed flag, secret input, root entrypoint, test mode, or direct command verification.
---

# Python CLI Developer

Read `references/python-script.md` and `references/cli.md` completely.

Use the canonical project parser provider when the project declares one. Keep secrets environment-only, environment binding explicit and validated, entrypoints directly runnable, and top-level run ownership contiguous.

Run the affected command directly, including `--help`, and follow the project-specific test-mode and catalog contract.
