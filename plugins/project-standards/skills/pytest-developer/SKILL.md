---
name: pytest-developer
description: Use when adding, changing, moving, running, or reviewing Python tests, fixtures, pytest configuration, behavior coverage, or code-contract checks.
---

# Pytest Developer

Read `references/test.md` completely.

Keep tests owner-local, deterministic, behavior-focused, and runnable through the owning repository's canonical pytest entrypoint. Cover success, the contract-defining failure, and critical introduced branches.

Do not assert instruction prose or use weaker surrogate tests in place of required real behavior verification.
