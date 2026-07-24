# Standard Submodule List Rules

- A governed project MUST list every concrete standard `Submodule` root represented in its `Key Directory Map`.
- Each entry MUST state the canonical submodule name, root path, exact submodule-owned host contract path, and only those applicability or integration constraints that are specific to the consuming project.
- The submodule's `DESIGN.md` or a document routed by it under `design/**` is the canonical owner of that submodule's stable purpose, public interface, and reusable host-integration contract.
- `Submodule AGENTS.md` governs work inside the submodule boundary and MUST NOT own rules for host code outside that boundary.
- A consuming project MUST reference the submodule-owned contract and MUST NOT copy or paraphrase it.
- A consumer entry MAY add a project-local specialization only within that consuming project's boundary and only under `External Standard Reference Rules`.
- A consumer block MUST NOT be shortened or removed until the referenced submodule-owned contract exists and has passed semantic verification.
