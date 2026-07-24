---
name: runtime-config-developer
description: Use when a project reads environment values, loads dotenv files, defines runtime configuration objects, establishes configuration precedence, or transports secrets.
---

# Runtime Config Developer

Read `references/configuration.md` completely.

Keep process environment authoritative, preserve present empty strings, use `None` only for a real absence value, fail on malformed present values, and keep secrets out of argv, help values, logs, and diagnostics.

Use explicit project-root loading and construct validated configuration before concurrent work starts.
