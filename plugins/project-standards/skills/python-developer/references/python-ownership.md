# Python Visibility And Ownership

## Applicability

These rules apply to non-`Legacy`, non-test Python code outside `Submodule` code.

## Visibility Contract

- In owner-controlled code, one symbol MUST be private by default.
- One symbol MAY be public only when one real use site exists outside that module or one external contract explicitly requires public visibility.
- One public symbol with no real use sites outside its module and no external-contract reason is forbidden and MUST be demoted to private.
- One private symbol that gains real use sites outside its module MUST be promoted to the correct public owner in the same change.

## Dead Code Contract

- This contract is repository-local use-site based: only in-repository use sites count.
- Repository-local dead private helpers are forbidden.
- A private module-level function or private receiverless helper method with no real in-repository use site MUST be deleted or refactored away in the same change instead of being kept for possible future use.
- Future-use placeholders are forbidden.

## Ownership And Placement Contract

- Every new module, class, function, or data object in changed scope MUST have explicit stable ownership.
- Placement of functions and classes is a strict ownership contract, not a convenience choice.
- One function used only inside one module MUST be a private module-level function in that same module.
- One class used only inside one module MUST stay in that same module.
- Private classes are forbidden; file-local classes MUST stay non-private and rely on module-local placement instead of private naming.
- One function or class used by multiple modules inside the same `script/<workflow_name>/**` slice MUST live in one owner-local module inside that same slice.
- One function or class used by multiple modules inside one owner-local `tool/**` slice MUST live in one owner-local shared module inside that same tool slice, typically under `tool/lib/**`.
- Code used by multiple different root-repository owner-local slices MUST live under one canonical shared owner, usually `lib/**`, unless another existing owner root already owns that concern.
- The keep-in-`lib/<package>/**` versus move-into-one-owner-local-slice decision is package-scoped: one `lib/<package>/**` package used only by one root-repository owner-local slice MUST move into that owner-local slice as one whole package, and one otherwise shared `lib/<package>/**` package MUST NOT be split by moving one individual module, function, or class out only because that member has a narrower local use scope.
- One function or class whose behavior is specific to one `Submodule` MUST live in that `Submodule`; root-repository `lib/**` MUST NOT own `Submodule`-specific logic.
- One function or class shared by multiple `Submodule`s MUST live in the canonical shared `Submodule` owner for that concern, not in the root repository.
- When changing use sites make these rules point to a different owner, the implementation MUST move to that owner and all repository call sites MUST migrate in the same change.
- Repository-local location-preserving bridges such as proxy methods, wrapper functions, forwarding imports, and compatibility aliases are forbidden for such owner moves.
