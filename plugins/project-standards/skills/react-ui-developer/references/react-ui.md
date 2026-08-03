# React UI Contract

- Use the project's shared component system and declarative page, form, table, action, layout, routing, authorization, notification, and query abstractions.
- Repeated visual and interaction behavior has one shared component or contract. Per-page restyling and one-off copies are forbidden.
- Forms use the standard field, required marker, description, validation, error, and action-panel contracts.
- Tables use standard sorting, filtering, pagination, selection, actions, column resizing, horizontal overflow, detail panel, and full-width behavior where applicable.
- Product action visibility and enabled state derive only from generated backend capability metadata and row-level allowed actions.
- The typed generated contract of `GET /capability` is the only action-to-capability source. A handwritten or parallel frontend action map and hardcoded role checks are forbidden.
- Capabilities control presentation and MUST NOT replace backend authorization.
- Personal presentation preferences are account-scoped, never browser-global: the shared preference owner keys them by the stable authenticated account identifier so different authenticated accounts always have distinct records. Changing only `effective_zitadel_user_id` during Product delegation MUST NOT switch the authenticated account preference.
- One shared declarative route-error owner handles recoverable failures for every route; route modules declare concrete error state and MUST NOT instantiate page-local boundaries. Missing route access preserves the requested URL and shell and presents a concrete access error. Other route failures preserve the shell and unaffected content instead of the framework default or a blank page.
- User-visible changes are verified through the complete affected workflow in a current real browser surface serving the current built and deployed assets after required UI tests and build.
- Real-browser verification MUST cover the changed action, every affected state transition, the recovery or reset path, and every user-visible success and failure outcome changed by the task.
- A dev server, local build files, source inspection, direct asset requests, route stubs, unit or `jsdom` tests, static screenshots, backend-only checks, and a browser tab that still holds stale JavaScript MUST NOT replace required current-assets browser verification.
- Visual debugging and visual fixes MUST compare the broken-before element, an analogous existing element that represents the intended standard, and the fixed-after element through screenshots.
- When browser, build, cache, session, data, environment, or service state prevents trustworthy verification, remediate that environment and rerun the complete real-browser workflow before handoff.
