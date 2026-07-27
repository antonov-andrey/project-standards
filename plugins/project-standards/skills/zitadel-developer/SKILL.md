---
name: zitadel-developer
description: Develop ZITADEL deployment, OIDC, tokens, identity clients, account switching, delegation, telemetry, or persistence.
---

# ZITADEL Developer

Read `references/zitadel.md` completely.

Keep one immutable ZITADEL subject as authorization identity, one shared OIDC session owner, one shared direct identity client, and explicit current-versus-effective identity semantics.

Apply `project-standards:http-api-client-developer` to outbound identity calls, `project-standards:runtime-config-developer` to identity configuration and secrets, `project-standards:react-ui-developer` to React presentation, and `project-standards:rest-api-server-developer` to Product API authorization and delegation.
