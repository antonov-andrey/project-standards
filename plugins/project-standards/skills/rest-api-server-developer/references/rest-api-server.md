# REST API Server Contract

- Every route is registered through the project's canonical router and declares whether it is product or infrastructure API.
- Authentication and authorization are checked before domain logic. Frontend visibility does not replace backend access control.
- OpenAPI security and route metadata match the actual access declaration and include useful descriptions for parameters, bodies, schemas, and responses.
- Request and response fields preserve canonical persisted or domain field identities unless a real external protocol owns another name.
- Product schemas expose only intended contract fields and do not leak service-only lifecycle fields or raw secrets.
- User-facing clients receive the concrete controlling validation, authentication, network, or backend error without stack traces or generic replacement wrappers.
- Database sessions are explicit dependencies with one request-scoped owner; middleware and audit logging do not reuse handler-owned sessions.
- Public, protected, delegated-user, and infrastructure boundaries remain explicit and auditable.
- One explicitly designed secret-bearing response may return short-lived credentials only with no-store caching and exclusion from body capture, logs, telemetry, and ordinary audit payloads.
