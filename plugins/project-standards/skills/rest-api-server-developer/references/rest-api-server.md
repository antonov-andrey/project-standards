# REST API Server Contract

## Table Of Contents

- [Placement And Registration](#placement-and-registration)
- [Standard Resource Mechanics](#standard-resource-mechanics)
- [Access And ZITADEL Delegation](#access-and-zitadel-delegation)
- [OpenAPI, Schemas, And Errors](#openapi-schemas-and-errors)
- [Sessions And Infrastructure Isolation](#sessions-and-infrastructure-isolation)
- [Capabilities](#capabilities)
- [Request Audit And Correlation](#request-audit-and-correlation)
- [Secret Responses](#secret-responses)
- [Extension](#extension)
- [Verification](#verification)

## Placement And Registration

- Concrete route modules, route-local request and response schemas, and route-local helpers live under `backend/api/**`.
- Files under `backend/**` outside `backend/api/**` MAY own application bootstrap, runtime dependency wiring, backend configuration, canonical router infrastructure such as `backend/api_router.py`, boundary validation such as `backend/validate.py`, and the package surface. They MUST NOT own concrete route entrypoints or route-local schemas.
- Every backend route is registered through `ProductApiRouter` and declares whether it is Product API or infrastructure API.
- `ProductApiResource` is the declarative standard-resource mechanism for `create`, `list`, `get`, `update`, `delete`, `archive`, `block`, `publish`, generated delegated variants, capabilities, and OpenAPI.
- `ProductApiRouter` is the unique-command and route-registry mechanism.
- Handwritten standard CRUD routes, handwritten delegated variants, and route-local bypasses around the canonical registry are forbidden.

## Standard Resource Mechanics

- Declared exact-equality list filters apply over owner scope before lifecycle filters, pagination, and status counts.
- Lifecycle and declared parent relations are checked before domain mutation. Read remains available only where the declared lifecycle permits it.
- Management `list`, `get`, and `update` remain constrained to the effective owner even for an administrator principal.
- Published foreign objects are exposed only through one separate minimal read-only selector boundary.
- A selector MUST NOT expose foreign management state, build history, credentials, logs, or another owner's mutable representation.
- For one standard mutable Product resource:
  - the owner can archive its writable object and unarchive its archived object;
  - an administrator can block, unblock, and delete;
  - a resource-specific override MUST NOT weaken administrator-only block, unblock, or delete access;
  - archived and blocked objects remain readable but otherwise immutable;
  - delete is an immediately hidden soft-delete, does not wait for external cleanup, and Product API exposes no restore route.

## Access And ZITADEL Delegation

- Route access is declared and evaluated before domain logic.
- Public access is declared explicitly through `ProductApiAccess.from_public()`.
- Role-restricted access is declared explicitly through `ProductApiAccess.from_role(...)`; multiple roles form one OR allowlist.
- When `project-standards:zitadel-developer` applies, Product API uses authenticated active ZITADEL bearer-token access by default and role decisions use only the current validated identity context.
- Product API MUST NOT create a duplicate local `user` role.
- When `project-standards:zitadel-developer` applies:
  - user-resource domain logic executes against `effective_zitadel_user_id`;
  - an ordinary request requires `effective_zitadel_user_id` to equal the current authenticated `zitadel_user_id`;
  - `ProductApiRouter` generates an `admin`-restricted delegated route under the reserved root prefix `/for-user/{zitadel_user_id}` for every user-resource Product route;
  - the generated route takes `effective_zitadel_user_id` from the root path parameter and verifies through ZITADEL that the effective user exists and is active before domain execution;
  - access metadata and delegated-route generation remain independent, so a role-restricted user-resource route still receives its generated delegated route;
  - protected non-user-resource routes and administrator routes without effective-user resource context MUST NOT generate delegated routes.
- The root literal path segment `for-user` is reserved for generated administrator-on-behalf-of-user routes.
- An administrator-only route without effective-user resource context is declared as a non-user-resource administrator route and MUST NOT use the `/for-user/{zitadel_user_id}` prefix.
- Ordinary resource-id path parameters MUST NOT intercept reserved root literal path segments.
- Client-supplied capabilities, roles, or effective owners MUST NOT be used as authorization input.

## OpenAPI, Schemas, And Errors

- OpenAPI security metadata matches the route access declaration.
- Every route registers its OpenAPI metadata through `ProductApiRouter` or `ProductApiResource`.
- Every route provides a summary, description, stable tags, a response description when a response body exists, and descriptions for every path, query, header, form, body, request-schema field, and response-schema field.
- `/openapi.json` is sorted by URL path and uses the HTTP method order `GET`, `POST`, `PATCH`, `DELETE`.
- Request and response fields preserve canonical persisted or domain field identities unless one explicit external protocol owns another name.
- Product schemas expose only intended contract fields and MUST NOT expose service-only fields such as `is_deleted`.
- A boundary-local request or response schema is allowed only for one operation payload, explicit external protocol, or declared secret-bearing response and MUST NOT become a second canonical resource model.
- Field-renaming mapper layers for canonical persisted fields are forbidden.
- Product responses preserve canonical persisted values except for conversion required by JSON serialization, transport safety, or one explicit external protocol.
- User-facing clients receive the concrete controlling validation, authentication, network, or backend error without stack traces or generic replacement wrappers.

## Sessions And Infrastructure Isolation

- Product API database sessions are explicit FastAPI dependencies and explicit function, method, or service parameters.
- A dependency that yields one SQLAlchemy session uses `scope="function"` unless one streaming response intentionally owns that session while streaming.
- Product API MUST NOT transport sessions through `Request.state`, `app.state`, context variables, globals, scoped-session registries, or another implicit request-local channel.
- Middleware and audit logging MUST NOT reuse handler-owned sessions. Post-handler database work opens its own session after handler-scoped dependencies have closed.
- Infrastructure routes MUST NOT access Product data, Product SQLAlchemy sessions, Product auth context, or Product domain services.
- Persistence and transaction semantics remain owned by `project-standards:sqlalchemy-developer`.

## Capabilities

- Product capabilities derive from the same route registry and are exposed through `GET /capability`; a parallel policy list is forbidden.
- Capabilities control presentation but never replace server-side authorization.
- Capability keys represent Product actions or modes and MUST NOT be role names.
- Optional `ProductApiAction` metadata carries exact `resource_key` and `action_key` and is exposed as `product_action`.
- `product_action=null` represents the deliberate absence of a Product UI action.
- Route registration validates uniqueness and rejects conflicting capability-to-action or action-to-capability mappings.

## Request Audit And Correlation

- Public routes are excluded from `ApiRequestLog`; their arrivals use ordinary runtime logging with method, path, request id, and response status.
- Protected Product API requests that reach a route handler are written to `ApiRequestLog`.
- `ApiRequestLog` stores current authenticated `zitadel_user_id` and `effective_zitadel_user_id` when ZITADEL identity applies.
- JSON request and response bodies are captured without truncation, except for an explicitly declared secret-bearing response boundary and the root `/api-request-log` response body.
- Multipart, upload, binary, and streaming bodies are not captured.
- Request and response headers are stored only after credential-bearing headers are redacted.
- Credential-bearing headers include `Authorization`, `Cookie`, `Set-Cookie`, `Proxy-Authorization`, `X-Api-Key`, and owner-declared authentication or secret-transport headers.
- Persisted or exposed audit header maps use the canonical names `request_header_map` and `response_header_map` with `dict[str, str]` semantics across ORM, database, and Product API surfaces.
- The server validates a supplied Product request id or generates a UUID when it is absent or invalid.
- The canonical request id is stored in runtime and audit records and echoed in every Product response.

## Secret Responses

- Ordinary Product JSON payloads MUST NOT carry raw credentials, keys, access tokens, private keys, or other raw secrets.
- One explicitly declared secret-bearing response boundary MAY return short-lived credentials only when it:
  - is registered through `ProductApiRouter`;
  - sets `Cache-Control: no-store`;
  - excludes its response body from `ApiRequestLog`, middleware body capture, caches, telemetry, and ordinary logs;
  - records only non-secret audit metadata.
- Secret-bearing Product flows use this boundary instead of ordinary JSON payloads.

## Extension

- Add one unique command when its state transition is not expressible as one standard resource action.
- Add one boundary-local schema only when an operation payload or explicit external protocol requires it.
- Add one infrastructure route only when the route has no Product data, Product auth context, Product session, or Product domain-service dependency.
- Concrete Product actions, role allowlists beyond standard administrator delegation, selector eligibility, domain lifecycle guards, capability keys, and route paths remain project-local.
- This skill owns the reusable behavior contract, not a copied runtime implementation. Before a second project implements the same `ProductApiRouter` runtime, establish one reusable runtime owner and migrate the existing implementation; a parallel or copied implementation is forbidden.

## Verification

- Behavior and code-contract verification MUST detect route bypass, missing access metadata, OpenAPI divergence, delegated-route mistakes, reserved-path interception, capability-map divergence, audit leakage, and secret-response capture.
