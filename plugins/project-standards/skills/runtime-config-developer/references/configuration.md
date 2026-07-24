# Runtime Configuration Contract

- Root bootstrap loads project configuration exactly once before constructing runtime objects or starting concurrent work.
- Dotenv loading receives an explicit project root and never searches ancestor directories.
- Precedence from strongest to weakest is process environment, local secret values, development values, and tracked non-secret defaults.
- A lower-priority source never overwrites a present process value.
- Present `''` is preserved. A default is used only when a key is absent.
- Typed readers reject malformed present values and identify only the configuration key, never its value.
- `None` means absence only when the domain requires a separate absence value.
- Secret classification is explicit, not inferred from a field name. Credentials, tokens, passwords, private keys, and equivalent values do not appear in argv, help values, repr, serialization, errors, logs, or ordinary telemetry.
- Validated configuration models own required fields, cross-field invariants, derived values, and domain constraints. Surrounding call sites do not duplicate normalization or fallback behavior.
- Package import performs no environment mutation or runtime resource construction.
