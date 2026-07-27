---
name: python-retry-developer
description: Design Python retry boundaries, backoff, repeat safety, and retryable exception or result classification.
---

# Python Retry Developer

Read `references/retry.md` completely.

Place one retry boundary around the smallest complete operation proven safe to repeat. Trace side effects, mutable state, timeout, idempotency, and ambiguous failures before changing any retry call site.

Use `retry_runtime/DESIGN.md` when that provider applies. Never retry `BaseException`, cancellation, process-control flow, or non-idempotent operations by default.
