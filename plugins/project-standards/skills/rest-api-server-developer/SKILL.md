---
name: rest-api-server-developer
description: Develop inbound HTTP routes, OpenAPI, schemas, authorization, access control, validation, and server boundaries.
---

# REST API Server Developer

Read `references/rest-api-server.md` completely and apply `project-foundation/references/temporal-data.md` to API instants.

Declare access before domain execution, keep documentation synchronized with actual routes, preserve canonical field identities, and keep authentication, secret, session, and audit boundaries explicit.

Apply `project-standards:zitadel-developer` when the Product API uses ZITADEL identity, and apply `project-standards:sqlalchemy-developer` to persistence and session behavior. Keep only concrete Product actions, role allowlists beyond standard admin delegation, selector eligibility, domain lifecycle guards, capability keys, and route paths in the project overlay.
