# ZITADEL Contract

## Identity And Session Boundary

- One shared owner manages the OIDC session, token lifecycle, login, account switch, renewal, logout, and identity-context cleanup.
- A governed React UI uses `react-oidc-context` as the OIDC session owner and exposes normalized identity through one shared provider boundary.
- The immutable ZITADEL subject or user id is the authorization identity. Email, name, login hint, and labels are presentation values only.
- Server-side Product access validates or introspects the current bearer token and confirms an active identity.
- Role decisions derive only from the current validated identity context.

## Direct ZITADEL API

- One shared direct ZITADEL API client owns identity protocol operations.
- Page-local and route-local ZITADEL protocol implementations are forbidden.
- Ordinary browser identity operations call ZITADEL through the shared direct client rather than through a Product backend proxy.
- Profile links use explicit identity inputs and MUST NOT use a hidden current-user fallback.
- Outbound transport behavior belongs to `project-standards:http-api-client-developer`, and environment-backed configuration and secrets belong to `project-standards:runtime-config-developer`.

## Current And Effective Identity

- Current authenticated `zitadel_user_id` and Product `effective_zitadel_user_id` remain explicit separate values.
- An ordinary Product request uses the current authenticated identity as the effective identity.
- Product delegation MAY change `effective_zitadel_user_id` for one explicit Product operation but MUST NOT change the browser principal.
- Product delegation MUST NOT implicitly enter direct identity API calls.
- Direct identity operations remain scoped to the authenticated principal unless the identity API operation explicitly defines administrator semantics.

## Secret And Telemetry Safety

- Tokens, authorization codes, state, nonce, cookies, private keys, credentials, raw callback URLs, and callback query strings MUST NOT enter persistence, ordinary logs, telemetry, Product URLs, or ordinary caches.
- Identity telemetry carries immutable ids and safe normalized stages instead of email, name, login hint, or raw protocol material.
- Product observability is limited to Product-owned OIDC stages and MUST NOT instrument ZITADEL pages or cross-origin silent-renew content.
- Product browser telemetry MUST NOT claim complete ZITADEL observability; ZITADEL server behavior remains owned by ZITADEL logs and metrics.

## Persistence And Lifecycle

- ZITADEL identity persistence remains independent from destructive Product-state reset.
- Product-state reset MUST NOT delete ZITADEL users, password state, provider links, or role assignments.
- Login, account switch, renewal, logout, and callback failures clear or replace identity context at their explicit lifecycle boundary so one session cannot leak identity into another.

## Extension

- Extend the shared boundary only through one normalized identity value needed by multiple consumers, one direct ZITADEL API operation in the shared client, or one new identity provider behind the same normalized boundary.
- Product-specific database names, deployment values, local users, Product role grants, storage session tags, secret-owner policies, and domain grants remain project-local.

## Verification

- Verification covers successful login and API use, invalid or inactive identity, renewal failure, current/effective separation, direct-identity isolation from Product delegation, secret redaction, explicit profile-link identity, identity-context cleanup, and identity persistence across Product-state reset.
- When the Product owns browser observability, verification confirms that its tracker is absent from ZITADEL pages and cross-origin silent-renew content.
