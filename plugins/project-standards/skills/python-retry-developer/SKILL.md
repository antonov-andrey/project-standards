---
name: python-retry-developer
description: Use when Python code adds or changes retry policy, retry loops, backoff, retryable exception or result classification, transport retries, or an operation that may execute more than once.
---

# Python Retry Developer

Read `references/retry.md` completely.

Place one retry boundary around the smallest complete operation proven safe to repeat. Trace side effects, mutable state, timeout, idempotency, and ambiguous failures before changing any retry call site.

Use `retry_runtime/DESIGN.md` when that provider applies. Never retry `BaseException`, cancellation, process-control flow, or non-idempotent operations by default.
