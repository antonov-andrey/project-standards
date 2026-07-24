---
name: http-api-client-developer
description: Use when code adds or changes an outbound HTTP integration, API client, endpoint mapping, external schema, provider error handling, rate limiting, or endpoint retry semantics.
---

# HTTP API Client Developer

Read `references/http-api-client.md` completely and apply `project-foundation/references/temporal-data.md` to external instants.

Each concrete integration owns authentication, endpoints, payloads, statuses, schemas, provider errors, quota scopes, idempotency, and lifecycle. Expose domain operations rather than generic public HTTP verbs or generic base-client inheritance.

Use the shared transport and schema providers selected by the project without duplicating their contracts.
