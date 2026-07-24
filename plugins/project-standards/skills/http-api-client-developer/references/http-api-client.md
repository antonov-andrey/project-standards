# HTTP API Client Contract

Each concrete external integration owns authentication, endpoint locations, request and response contracts, accepted status codes, provider errors, quota scopes, and endpoint idempotency.

Shared Requests transport, timeout, and transport retry use `retry_runtime/DESIGN.md`. Shared external response-schema behavior uses `base_api_schema/DESIGN.md`.

A public integration client exposes endpoint or domain operations. Public generic HTTP verb methods and generic base-client inheritance are forbidden.

Each endpoint operation defines its HTTP method, path, payload or parameters, accepted statuses, response type, error mapping, retry boundary, and side-effect semantics.

Provider-specific rate limiting remains inside that integration and is keyed by the provider's real quota scope rather than hostname alone.

One Session has an explicit lifecycle owner. Credentials, payloads, URL user information, query strings, raw response bodies, and raw external exception text are not logged.

Transport failure, timeout, unexpected status, invalid response syntax, provider error response, item rejection, and ambiguous mutation outcome remain distinguishable.
