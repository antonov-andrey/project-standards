# Machine-Readable Format Contract

- Use YAML for one project-owned human-maintained machine-readable file when no external ecosystem, protocol, or tool makes another format more idiomatic.
- Use the `.yaml` extension. Do not create `.yml` files.
- Use JSON when an external JSON API, JSON Schema, OpenAPI artifact, package manager, browser tool, generated client, fixture contract, or canonical byte-oriented interchange requires JSON.
- Use TOML when an owning ecosystem or tool defines TOML as its canonical configuration surface, including `pyproject.toml`, `Cargo.toml`, and provider-owned tool manifests.
- Do not convert a file only for visual uniformity when its current external consumer owns another format.
- Project-owned YAML uses UTF-8, YAML 1.2 semantics, and exactly one document.
- Project-owned YAML parsers must reject duplicate keys, custom tags, anchors, aliases, merge keys, and unknown fields in a closed schema.
- Do not use YAML implicit typing when the field contract requires one exact string. Quote that value or validate its parsed type at the boundary.
- A textual field with no distinct absence state uses the canonical empty string `""`; use `null` only when absence is a separate domain value that the schema and consumers intentionally distinguish.
