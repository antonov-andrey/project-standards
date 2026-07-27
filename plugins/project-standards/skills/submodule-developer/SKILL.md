---
name: submodule-developer
description: Add, change, consume, publish, rename, remove, or document Git submodules and provider contracts.
---

# Submodule Developer

Read `references/submodule-model.md` and `references/submodule-registry.md` completely.

Treat each submodule as a sibling repository boundary with its own code, instructions, tools, tests, design, revision, and publication lifecycle. Keep host bindings explicit and provider contracts in the owning submodule.

Publish and verify the submodule first; update consumer gitlinks only after provider and consumer compatibility checks pass.
