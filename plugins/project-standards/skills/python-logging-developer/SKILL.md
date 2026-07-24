---
name: python-logging-developer
description: Use when a project configures, writes, parses, rotates, or transports Python logging records, or when one changed runtime adds a Python logging bootstrap.
---

# Python Logging Developer

Read `references/logging.md` completely.

Use `config_logging/DESIGN.md` as the provider contract when the submodule is present. Initialize standard logging once at root bootstrap, then use direct `import logging` calls without logger objects, hidden configuration, or unrelated artifact ownership.
