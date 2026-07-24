# React UI Contract

- Use the project's shared component system and declarative page, form, table, action, layout, routing, authorization, notification, and query abstractions.
- Repeated visual and interaction behavior has one shared component or contract. Per-page restyling and one-off copies are forbidden.
- Forms use the standard field, required marker, description, validation, error, and action-panel contracts.
- Tables use standard sorting, filtering, pagination, selection, actions, column resizing, horizontal overflow, detail panel, and full-width behavior where applicable.
- Product actions derive visibility and enabled state from backend capability metadata rather than hardcoded roles.
- Account-scoped presentation preferences remain scoped to the effective account when the product uses delegated accounts.
- Route failures preserve the shell and unaffected content. A route error boundary presents a recoverable concrete error instead of the framework default or a blank page.
- User-visible changes are verified through the complete affected workflow in a current real browser surface after tests and build.
