---
name: react-ui-developer
description: Develop or review React views using shared form, table, layout, route, theme, account preference, and error-boundary contracts.
---

# React UI Developer

Read `references/react-ui.md` completely and apply `typescript-developer`.

Use shared standard components and declarative contracts, preserve one owner for repeated UI behavior, and verify the complete affected workflow in a real browser after required tests and build.

Table behavior and recoverable route errors belong to shared declarative owners, never page-local implementations.

Presentation preferences use one shared account-scoped owner keyed by the stable authenticated account identifier: different authenticated accounts always have distinct records, while changing only an effective delegated user does not switch the authenticated account preference.

Do not replace backend authorization with hidden frontend controls or replace concrete errors with generic wrappers.
