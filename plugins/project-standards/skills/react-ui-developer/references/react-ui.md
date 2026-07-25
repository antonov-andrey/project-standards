# React UI Contract

- Use the project's shared component system and declarative page, form, table, action, layout, routing, authorization, notification, and query abstractions.
- Repeated visual and interaction behavior has one shared component or contract. Per-page restyling and one-off copies are forbidden.
- Forms use the standard field, required marker, description, validation, error, and action-panel contracts.
- Tables use standard sorting, filtering, pagination, selection, actions, column resizing, horizontal overflow, detail panel, and full-width behavior where applicable.
- Product action visibility and enabled state derive only from generated backend capability metadata and row-level allowed actions.
- The typed generated contract of `GET /capability` is the only action-to-capability source. A handwritten or parallel frontend action map and hardcoded role checks are forbidden.
- Capabilities control presentation and MUST NOT replace backend authorization.
- Personal presentation preferences remain scoped to the authenticated identity. Changing only `effective_zitadel_user_id` during Product delegation MUST NOT change them.
- Missing route access preserves the requested URL and shell and presents a concrete access error. Other route failures preserve the shell and unaffected content through a recoverable concrete error boundary instead of the framework default or a blank page.
- User-visible changes are verified through the complete affected workflow in a current real browser surface after tests and build.
