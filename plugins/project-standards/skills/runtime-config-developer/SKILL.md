---
name: runtime-config-developer
description: Develop environment loading, runtime configuration, precedence, dotenv handling, or secret transport.
---

# Runtime Config Developer

Read `references/configuration.md` completely.

Keep process environment authoritative, preserve present empty strings, use `None` only for a real absence value, fail on malformed present values, and keep secrets out of argv, help values, logs, and diagnostics.

Use explicit project-root loading and construct validated configuration before concurrent work starts.
