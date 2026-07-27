---
name: python-logging-developer
description: Develop Python logging configuration, records, parsing, rotation, transport, or runtime bootstrap.
---

# Python Logging Developer

Read `references/logging.md` completely.

Use `config_logging/DESIGN.md` as the provider contract when the submodule is present. Initialize standard logging once at root bootstrap, then use direct `import logging` calls without logger objects, hidden configuration, or unrelated artifact ownership.
