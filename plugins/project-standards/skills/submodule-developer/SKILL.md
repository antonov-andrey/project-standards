---
name: submodule-developer
description: Use when adding, changing, consuming, publishing, renaming, removing, or documenting a Git submodule or its reusable provider contract.
---

# Submodule Developer

Read `references/submodule-model.md` and `references/submodule-registry.md` completely.

Treat each submodule as a sibling repository boundary with its own code, instructions, tools, tests, design, revision, and publication lifecycle. Keep host bindings explicit and provider contracts in the owning submodule.

Publish and verify the submodule first; update consumer gitlinks only after provider and consumer compatibility checks pass.
