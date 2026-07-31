# Code Antipattern Audit Semantic Cards

## Table Of Contents

- [Book Anti-Pattern Cards (General)](#book-anti-pattern-cards-general)
  - [BOOK-01 The Blob](#book-01-the-blob)
  - [BOOK-02 Spaghetti Code](#book-02-spaghetti-code)
  - [BOOK-03 Cut-and-Paste Programming](#book-03-cut-and-paste-programming)
  - [BOOK-04 Lava Flow](#book-04-lava-flow)
  - [BOOK-05 Functional Decomposition (OO context)](#book-05-functional-decomposition-oo-context)
  - [BOOK-06 Poltergeists](#book-06-poltergeists)
- [Opinionated Project Anti-Pattern Cards](#opinionated-project-anti-pattern-cards)
  - [PRJ-01 God Composition Root](#prj-01-god-composition-root)
  - [PRJ-02 Domain Modules Import Infrastructure Libraries](#prj-02-domain-modules-import-infrastructure-libraries)
  - [PRJ-03 Hidden Dependency Construction Inside Orchestration Classes](#prj-03-hidden-dependency-construction-inside-orchestration-classes)
  - [PRJ-04 Service Locator / Dynamic Wiring Hacks](#prj-04-service-locator--dynamic-wiring-hacks)
  - [PRJ-05 Cross-Script Imports for New Business Logic Reuse](#prj-05-cross-script-imports-for-new-business-logic-reuse)
  - [PRJ-06 Ceremonial Layering Without Concrete Problem](#prj-06-ceremonial-layering-without-concrete-problem)
  - [PRJ-07 Copy-Pasted Helper Logic Across Modules/Classes](#prj-07-copy-pasted-helper-logic-across-modulesclasses)
  - [PRJ-08 Argument-Pack / Pseudo-Method Helpers](#prj-08-argument-pack--pseudo-method-helpers)
  - [PRJ-09 Loop-Invariant Work Inside Per-Item Loops](#prj-09-loop-invariant-work-inside-per-item-loops)
  - [PRJ-10 Pass-through Proxy Methods](#prj-10-pass-through-proxy-methods)
  - [PRJ-11 Anemic Entity Model / Transaction Script](#prj-11-anemic-entity-model--transaction-script)
  - [PRJ-12 Ceremonial Ports / Interface-For-One-Class](#prj-12-ceremonial-ports--interface-for-one-class)
  - [PRJ-13 DTO Conveyor Belt](#prj-13-dto-conveyor-belt)
  - [PRJ-14 Generic Bucket Modules / Stage-Named Structure](#prj-14-generic-bucket-modules--stage-named-structure)
  - [PRJ-15 Single-Use Artifacts Without Stable Ownership](#prj-15-single-use-artifacts-without-stable-ownership)
  - [PRJ-16 Overloaded Control Flow Without Cohesive Owner](#prj-16-overloaded-control-flow-without-cohesive-owner)
  - [PRJ-17 Dependency Fan-Out Beyond Owner Role](#prj-17-dependency-fan-out-beyond-owner-role)

## Book Anti-Pattern Cards (General)

### BOOK-01 The Blob
Positive match:
- One owner class or module centralizes multiple unrelated responsibilities or most orchestration in the declared scope.
- Neighboring owners are mostly passive data holders, thin wrappers, or other low-behavior artifacts.
- The dominant owner controls behavior that should be partitioned across several stable owners.
Required evidence:
- File or line evidence of one dominant owner plus at least two passive or near-passive neighboring owners.
- A clear mismatch between concentrated behavior and stable ownership boundaries.
Negative match:
- A thin `composition root`.
- One large but cohesive algorithm owner.
- One boundary translator that is large only because of one stable translation contract.
Competing cards:
- Prefer `PRJ-01` when the overloaded owner is the `composition root`.
- Prefer `PRJ-11` when the main defect is data-only entity or workflow-state ownership.
- Prefer `BOOK-02` when the main defect is tangled control flow rather than concentrated responsibility.
Scope expansion:
- Inspect direct collaborators of the dominant owner.
- Inspect the immediate caller and callee chain around that owner.
Refactor direction:
- Split responsibilities into cohesive collaborators.
- Move behavior closer to stable owners of state and boundary rules.
Exceptions:
- None in this repository.

### BOOK-02 Spaghetti Code
Positive match:
- Control flow in the declared scope is hard to follow because stage boundaries, ownership boundaries, or dependency direction are unclear.
- Objects or modules mostly participate in one long predictable process chain with weak or confusing relationships.
- Modifying one stage tends to require touching distant unrelated stages.
Required evidence:
- File or line evidence of tangled multistage control flow or unstable module boundaries.
- Evidence that the current owner split does not explain the runtime flow clearly.
Negative match:
- One cohesive pipeline with clear stage owners and stable boundaries.
- One complex owner whose behavior is dense but still locally coherent.
Competing cards:
- Prefer `BOOK-05` when the main defect is transaction-script decomposition over passive owners.
- Prefer `PRJ-06` when the main defect is ceremonial layering around an otherwise clear flow.
- Prefer `PRJ-14` when the main defect is a conveyor of near-identical data shapes.
Scope expansion:
- Inspect the full caller chain through the affected stages.
- Inspect adjacent owners that participate in the same flow.
Refactor direction:
- Normalize ownership boundaries and dependency direction.
- Split multistage flow into cohesive owners and add regression tests before moving logic.
Exceptions:
- Short-lived isolated prototypes that are explicitly marked and not reused.

### BOOK-03 Cut-and-Paste Programming
Positive match:
- Similar code blocks or helper implementations appear in multiple owners and evolve independently.
- The same defect, workaround, or update would need to be repeated in more than one place.
Required evidence:
- At least two code locations with materially duplicated behavior.
- Evidence that the duplicate logic is not owned by one shared stable owner yet.
Negative match:
- Intentional duplication for strict isolation with a documented owner and reason.
- Repeated shape that exists only because separate external boundaries require distinct contracts.
Competing cards:
- Prefer `PRJ-07` when the duplication is primarily private or helper logic across modules or classes.
- Prefer `PRJ-14` when the main defect is repeated data-shape mapping rather than repeated behavior.
Scope expansion:
- Inspect sibling modules and classes that solve the same narrow task.
- Inspect all active call sites that rely on the duplicated behavior.
Refactor direction:
- Extract one shared implementation and migrate all duplicate call sites.
- Convert repeated fixes into one canonical owner.
Exceptions:
- Intentional isolation with explicit owner and rationale.

### BOOK-04 Lava Flow
Positive match:
- The declared scope contains ownerless dead branches, obsolete modules, or abandoned logic that no one can justify as active current behavior.
- Code remains only because it is feared, forgotten, or left from old attempts.
Required evidence:
- File or line evidence that the path is obsolete, ownerless, or disconnected from current behavior.
- Evidence that the code is retained by inertia rather than by a current stable contract.
Negative match:
- Active behavior with a current owner and current verification.
- Explicit legal or compliance retention path with a clear access and lifecycle contract.
Competing cards:
- Prefer `BOOK-02` when the code is still active but tangled.
- Prefer `PRJ-05` when the main defect is wrong placement of reusable logic rather than dead residue.
Scope expansion:
- Inspect references, callers, and current runtime entrypoints for the suspicious path.
- Inspect nearby legacy branches that may be part of the same obsolete flow.
Refactor direction:
- Delete dead code in small safe batches.
- Replace fear-based retention with explicit current ownership or removal.
Exceptions:
- Compliance-required retention with an explicit current contract.

### BOOK-05 Functional Decomposition (OO context)
Positive match:
- Behavior and data are split into procedural helper owners instead of being colocated with stable state and invariants.
- Class or module structure mirrors functions or steps rather than real stable owners.
Required evidence:
- File or line evidence of transaction-script helpers that manipulate project state from outside its stable owner.
- Evidence that the current owner split is procedural rather than owner-based.
Negative match:
- Pure deterministic utilities that do not own repository state or business rules.
- Explicit boundary utilities that translate data without owning domain behavior.
Competing cards:
- Prefer `PRJ-11` when the main defect is specifically data-only entity or workflow-state owners.
- Prefer `BOOK-02` when the main defect is tangled flow rather than owner placement of behavior.
Scope expansion:
- Inspect the target owner whose state is being manipulated externally.
- Inspect sibling helper owners with the same procedural pattern.
Refactor direction:
- Move behavior into owners that hold the stable state and invariants.
- Rebuild modules around workflow, entity, or shared-owner concepts instead of step names.
Exceptions:
- Pure algorithm helpers that do not accept project entities or workflow-state owners.

### BOOK-06 Poltergeists
Positive match:
- A short-lived class or module exists only to invoke or delegate into longer-lived owners.
- The owner adds no stable state, boundary translation, cache, policy, or lifecycle behavior.
Required evidence:
- File or line evidence that the owner mostly forwards or seeds work for another owner.
- Evidence that the owner has no lasting responsibility beyond transient invocation.
Negative match:
- Mandatory framework adapters with real lifecycle or translation behavior.
- Boundary owners that exist to enforce a stable external contract.
Competing cards:
- Prefer `PRJ-10` when the defect is a pure pass-through method.
- Prefer `PRJ-06` when the defect is a whole ceremonial layer rather than one transient owner.
- Prefer `PRJ-12` when the defect is an interface or port introduced for one in-process collaborator.
Scope expansion:
- Inspect constructor state, lifecycle, and all public methods of the transient owner.
- Inspect the immediate target owners that actually do the work.
Refactor direction:
- Delete the transient owner and move the responsibility to the real stable owner.
- Remove redundant navigation paths.
Exceptions:
- Framework-mandated adapters with real boundary or lifecycle responsibility.

## Opinionated Project Anti-Pattern Cards

### PRJ-01 God Composition Root
Positive match:
- A `composition root` owns business logic, non-trivial transforms, or behavior decisions instead of composition-only wiring.
- The same owner both constructs collaborators and performs domain or workflow work.
Required evidence:
- File or line evidence that a `composition root` does more than bootstrap, wire, or hand off.
- Evidence of behavior decisions or non-trivial transforms in that same owner.
Negative match:
- Thin entrypoints and thin composition-root modules that only wire and hand off.
- Small startup guards that exist only to validate launch-time preconditions.
Competing cards:
- Prefer `BOOK-01` when the owner is not specifically a `composition root`.
- Prefer `PRJ-03` when the main defect is hidden dependency construction inside a non-root owner.
Scope expansion:
- Inspect the root entrypoint, the root helper, and the first downstream workflow owner.
- Inspect constructor wiring and top-level transforms together.
Refactor direction:
- Move behavior into dedicated workflow or boundary owners.
- Keep the `composition root` thin and contiguous.
Exceptions:
- None.

### PRJ-02 Domain Modules Import Infrastructure Libraries
Positive match:
- Workflow, entity, or shared-library owners import infrastructure libraries directly instead of confining those imports to boundary owners.
- The imported infrastructure shapes internal business logic directly.
Required evidence:
- File or line evidence of direct infrastructure imports in inner owners.
- Evidence that the same owner now depends on external transport, persistence, browser, or SDK concerns.
Negative match:
- Explicit boundary owners under stable boundary roles.
- Schema, transport, or integration owners whose job is to speak the external library.
Competing cards:
- Prefer `PRJ-03` when the main defect is hidden construction of a dependency rather than direct importing.
- Prefer `PRJ-04` when the main defect is dynamic runtime lookup of dependencies.
Scope expansion:
- Inspect the imported symbols and how they are used.
- Inspect the nearest boundary owners that should own the external dependency.
Refactor direction:
- Move infrastructure coupling to explicit boundary owners.
- Keep inner owners infrastructure-agnostic.
Exceptions:
- None.

### PRJ-03 Hidden Dependency Construction Inside Orchestration Classes
Positive match:
- An orchestration owner constructs sessions, clients, pages, repositories, or similar external dependencies inside working methods.
- The same owner both coordinates behavior and silently chooses dependency instances.
Required evidence:
- File or line evidence of dependency construction inside non-root orchestration flow.
- Evidence that constructor or explicit injection should own that dependency instead.
Negative match:
- Explicit `composition root` owners.
- Dedicated factories that exist only to create one stable dependency family.
- Test setup code.
Competing cards:
- Prefer `PRJ-04` when the main defect is late lookup through a locator or registry.
- Prefer `PRJ-17` when the main defect is too many dependencies in one owner rather than hidden construction.
Scope expansion:
- Inspect the owner constructor, fields, and method-local constructions together.
- Inspect the nearest wiring owner that should inject the dependency.
Refactor direction:
- Move construction to the `composition root` or dedicated factory owner.
- Inject the dependency through an explicit stable boundary.
Exceptions:
- None.

### PRJ-04 Service Locator / Dynamic Wiring Hacks
Positive match:
- Runtime dependency resolution happens through `globals()`, dynamic imports, registries, service locators, or mutable global wiring state.
- Business or workflow behavior depends on late runtime lookup instead of explicit stable injection.
Required evidence:
- File or line evidence of late dependency lookup.
- Evidence that the lookup participates in runtime behavior rather than bootstrap-only setup.
Negative match:
- Isolated framework bootstrap with no business-logic reach.
- Static registration that is resolved once in startup and not re-entered from business flow.
Competing cards:
- Prefer `PRJ-03` when the main defect is direct local construction instead of lookup.
- Prefer `PRJ-17` when the main defect is fan-out growth without dynamic lookup.
Scope expansion:
- Inspect the lookup call sites and the resulting collaborators.
- Inspect whether the same owner could instead receive a dependency explicitly.
Refactor direction:
- Replace locator-based resolution with explicit wiring.
- Keep runtime dependency choice in stable bootstrap owners only.
Exceptions:
- Framework bootstrap boundaries with explicit documentation and no business-logic reach.

### PRJ-05 Cross-Script Imports for New Business Logic Reuse
Positive match:
- New reusable business logic is imported directly from another script package or workflow-local package.
- Cross-script reuse is achieved by reaching into another script owner instead of extracting a shared owner.
Required evidence:
- File or line evidence of cross-script imports for reusable business behavior.
- Evidence that the imported logic is no longer owned by only one workflow family.
Negative match:
- Read-only legacy imports with an approved migration plan.
- Imports of tiny local CLI or startup helpers that are not business reuse.
Competing cards:
- Prefer `BOOK-03` or `PRJ-07` when the main defect is duplication rather than wrong reuse placement.
- Prefer `PRJ-06` when the main defect is an unnecessary wrapper layer added to hide wrong placement.
Scope expansion:
- Inspect the imported owner and all current callers of that logic.
- Inspect whether the logic belongs under `lib/**` or one shared workflow family owner.
Refactor direction:
- Extract shared logic into a dedicated shared owner and migrate callers.
- Stop treating one script package as a shared library.
Exceptions:
- Read-only legacy imports with explicit owner and migration plan.

### PRJ-06 Ceremonial Layering Without Concrete Problem
Positive match:
- A new `runtime`, `facade`, `adapter`, `manager`, or similar layer exists only for symmetry, naming, or ceremony.
- The layer does not solve a concrete boundary, lifecycle, cache, policy, or ownership problem.
Required evidence:
- File or line evidence that the layer mainly forwards, renames, repackages, or delegates.
- Evidence that deleting the layer would not remove a real stable responsibility.
Negative match:
- A layer that owns one explicit stable boundary, lifecycle, or translation contract.
- A layer that materially narrows or stabilizes an external dependency.
Competing cards:
- Prefer `PRJ-10` for a pure proxy method.
- Prefer `PRJ-12` for a one-class port or interface layer.
- Prefer `BOOK-06` for one transient ghost owner rather than a whole ceremonial layer.
Scope expansion:
- Inspect upstream and downstream owners that the layer sits between.
- Inspect whether the layer introduces any real invariant or boundary rule.
Refactor direction:
- Collapse the layer and keep the minimal architecture that solves a real problem.
- Move remaining behavior into the true stable owner.
Exceptions:
- None.

### PRJ-07 Copy-Pasted Helper Logic Across Modules/Classes
Positive match:
- Private or helper logic with identical or near-identical behavior is duplicated across modules or classes.
- The duplication is inside project helper or support logic, not only at an external boundary.
Required evidence:
- File or line evidence of duplicate helper logic across at least two owners.
- Evidence that one stable shared owner can own that behavior.
Negative match:
- Intentional strict isolation with an explicit owner and rationale.
- Distinct external boundaries that require materially different logic despite similar shape.
Competing cards:
- Prefer `BOOK-03` when the duplication is broader than helper logic.
- Prefer `PRJ-14` when the main defect is repeated data-shape mapping instead of repeated behavior.
Scope expansion:
- Inspect sibling helper owners and all duplicate call sites.
- Inspect whether one current owner is already the obvious shared home.
Refactor direction:
- Extract one shared helper owner and migrate all duplicates.
- Normalize bug fixes through one canonical implementation.
Exceptions:
- Intentional strict isolation with explicit rationale.

### PRJ-08 Argument-Pack / Pseudo-Method Helpers
Positive match:
- Helper signatures carry dependency packs such as `session`, `client`, `page`, `config`, `logger`, or similar external context.
- Methods proxy multiple `self.*` fields into helpers instead of reading owner state directly.
Required evidence:
- File or line evidence of dependency-pack signatures or pseudo-method callsites.
- Evidence that the behavior belongs in a collaborator owner or in the current owner's private methods.
Negative match:
- Pure deterministic helpers with no dependency-like arguments.
- Boundary translators whose explicit job is to convert one fully formed input to one fully formed output.
Competing cards:
- Prefer `PRJ-03` when the main defect is hidden construction.
- Prefer `PRJ-17` when the main defect is one owner coordinating too many dependencies rather than one helper signature.
Scope expansion:
- Inspect the helper signature, the calling owner, and the source of the forwarded fields.
- Inspect sibling helpers that carry the same pack.
Refactor direction:
- Convert the helper into a collaborator with constructor DI or into a private owner method.
- Read owner state from the owner instead of mirroring it through mandatory arguments.
Exceptions:
- Pure deterministic helpers without IO or dependency-like arguments.

### PRJ-09 Loop-Invariant Work Inside Per-Item Loops
Positive match:
- Shared DB, API, config, or precompute work repeats per item even though the inputs are invariant for the outer loop.
- The repeated work materially belongs outside the item loop.
Required evidence:
- File or line evidence of repeated invariant work inside an explicit or implicit per-item loop.
- Evidence that the repeated work does not depend on item-local state for correctness.
Negative match:
- Per-item recomputation required by correctness with explicit evidence.
- Small repeated work that is item-local and not meaningfully shareable.
Competing cards:
- Prefer `PRJ-17` when the main defect is owner fan-out rather than repeated invariant work.
- Prefer `BOOK-02` when the main defect is whole-flow entanglement rather than one hoisting defect.
Scope expansion:
- Inspect loop setup, invariant inputs, and downstream consumers of the repeated result.
- Inspect whether a precomputed context owner already exists or should exist.
Refactor direction:
- Hoist invariant work outside the loop and reuse the resulting context inside iteration.
- Introduce one stable owner for the shared precomputed context when needed.
Exceptions:
- Per-item recomputation required by correctness with documented evidence.

### PRJ-10 Pass-through Proxy Methods
Positive match:
- A method only forwards parameters to another method or owner without adding behavior, validation, normalization, caching, or boundary translation.
- The proxy exists only to preserve call shape or naming symmetry.
Required evidence:
- File or line evidence of a method whose body is effectively one forwarding call.
- Evidence that the proxy does not own a stable responsibility.
Negative match:
- Methods that add validation, normalization, cache, retry, translation, or policy.
- Methods that narrow or stabilize a real external boundary.
Competing cards:
- Prefer `BOOK-06` when a whole transient owner exists only to delegate.
- Prefer `PRJ-06` when a whole ceremonial layer exists around the forwarding method.
Scope expansion:
- Inspect the proxy body and the target owner it delegates to.
- Inspect sibling proxies in the same owner for a broader pattern.
Refactor direction:
- Delete the proxy and call the true owner directly.
- Move any remaining real behavior into the stable owner.
Exceptions:
- None.

### PRJ-11 Anemic Entity Model / Transaction Script
Positive match:
- Project entities or workflow-state owners are mostly data, while business rules, validation, calculations, or state transitions live in external functions.
- External functions read or mutate project state directly to perform business decisions.
Required evidence:
- File or line evidence of business rules operating on project state from outside its stable owner.
- Evidence that the affected entity or workflow-state owner does not currently own its invariants.
Negative match:
- DTO, transport, or schema containers at explicit boundaries.
- Pure utility helpers that do not accept project state owners and do not implement business rules.
Competing cards:
- Prefer `BOOK-05` when the main defect is broader procedural decomposition across the design.
- Prefer `BOOK-01` when one dominant controller monopolizes behavior across many passive owners.
Scope expansion:
- Inspect the affected state owner and the external functions that operate on it.
- Inspect sibling state transitions and calculations for the same pattern.
Refactor direction:
- Move invariants, calculations, validation, and transitions into the stable owner.
- Keep cross-owner operations in explicit bounded owners with one stable responsibility.
Exceptions:
- DTO, transport, and schema containers outside inner repository boundaries.
- Pure utility helpers that do not implement repository business rules.

### PRJ-12 Ceremonial Ports / Interface-For-One-Class
Positive match:
- A `Protocol`, `ABC`, or similar port is introduced for one in-process collaborator with one production implementation and no real boundary.
- The interface exists mainly for symmetry, tests, or speculative future reuse.
Required evidence:
- File or line evidence that the port has one in-process implementation in the current scope.
- Evidence that no current stable external boundary or current multi-implementation reason exists.
Negative match:
- Public reusable framework or library contracts.
- External-boundary interfaces or framework callback contracts owned outside repository business code.
Competing cards:
- Prefer `PRJ-06` when the main defect is a ceremonial layer rather than a ceremonial contract.
- Prefer `PRJ-10` when the main defect is a pass-through method without an interface layer.
Scope expansion:
- Inspect all implementations and all current consumers of the port.
- Inspect whether the same owner could be typed concretely without losing a real boundary.
Refactor direction:
- Collapse the interface layer or type the collaborator concretely.
- Keep ports only where a current real boundary or current multi-implementation reason exists.
Exceptions:
- Public reusable framework or library contracts.
- Framework callback contracts owned outside repository business code.

### PRJ-13 DTO Conveyor Belt
Positive match:
- The same payload moves through three or more near-identical shapes with little semantic gain.
- Intermediate mappings mostly rename fields or repackage values without validation, normalization, or new constraints.
Required evidence:
- File or line evidence of a multi-stage shape conveyor with near-identical fields.
- Evidence that the intermediate shapes do not own distinct boundary meaning.
Negative match:
- Serialization, API, DB, or schema boundaries with distinct external contracts.
- One translation step that genuinely adds validation, normalization, or semantic compression.
Competing cards:
- Prefer `PRJ-07` when the main defect is repeated helper behavior rather than repeated shapes.
- Prefer `BOOK-05` or `PRJ-11` when the main defect is ownerless business behavior rather than ownerless shapes.
Scope expansion:
- Inspect the full chain of shapes for one payload family.
- Inspect which stages are real boundaries and which are redundant repackaging.
Refactor direction:
- Collapse redundant shapes and keep one canonical owner until a real boundary requires translation.
- Move behavior into the richer stable owner instead of multiplying shape layers.
Exceptions:
- Serialization, API, DB, and schema boundaries with distinct external contracts.

### PRJ-14 Generic Bucket Modules / Stage-Named Structure
Positive match:
- Bucket names such as `models`, `services`, `utils`, `runtime`, `common`, or similar collect unrelated logic because ownership is organized by stage rather than concept.
- Understanding one business concept requires jumping across several generic buckets instead of reading one cohesive owner area.
- One overloaded module was split into many siblings in a broad directory, with the same subsystem prefix repeated in filenames instead of represented once by an owning package path.
Required evidence:
- File or line evidence of heterogeneous logic inside a bucket owner or across parallel stage buckets.
- Evidence that the current names hide stable domain or boundary ownership.
- For a flat prefixed file family, evidence that the files share one subsystem context and contain child responsibility families that can be named as package owners.
Negative match:
- Tiny cohesive package-local helpers.
- Package export surfaces.
- One small owner whose generic-looking name still maps to one stable boundary role in context.
Competing cards:
- Prefer `BOOK-02` when the main defect is tangled flow rather than bucket ownership.
- Prefer `PRJ-06` when the main defect is a ceremonial layer instead of a generic bucket owner.
Scope expansion:
- Inspect neighboring modules in the same package and the import mix of the bucket owner.
- Inspect whether one domain concept is split across several bucket owners.
Refactor direction:
- Re-slice modules by domain concept or stable technical role.
- Split generic buckets once they stop being tiny and cohesive.
- Create the smallest owning package for one cohesive subsystem, remove the repeated subsystem filename prefix, and introduce child subpackages only for real responsibility families rather than directory symmetry.
Exceptions:
- Tiny cohesive package-local modules.
- Package init export surfaces.

### PRJ-15 Single-Use Artifacts Without Stable Ownership
Positive match:
- A function, class, or module has only one meaningful caller or consumer and adds no stable invariant, boundary, cache, or non-trivial algorithm.
- The artifact exists mainly to preserve shape, naming, or ceremony around one caller.
Required evidence:
- File or line evidence of one meaningful caller or consumer in this repository.
- Evidence that the artifact adds no stable owner responsibility beyond forwarding or trivial repackaging.
Negative match:
- Explicit boundary adapters with one real external contract.
- One-call-site artifacts that still own a non-trivial algorithm, invariant, or lifecycle rule.
Competing cards:
- Prefer `PRJ-10` when the artifact is a pure pass-through method.
- Prefer `PRJ-06` when the artifact is part of a whole ceremonial layer.
Scope expansion:
- Inspect all call sites or consumers of the artifact.
- Inspect the nearest stable owner that could absorb the behavior directly.
Refactor direction:
- Inline, delete, or merge the artifact into the nearest stable owner.
- Keep separate artifacts only when they own a real stable responsibility.
Exceptions:
- Boundary adapters, caches, lifecycle owners, or non-trivial algorithm owners with one current caller.

### PRJ-16 Overloaded Control Flow Without Cohesive Owner
Positive match:
- A function or method has high branching or nesting because it mixes several concerns or policy families in one owner.
- The control flow is hard to understand because one owner carries too many unrelated decisions.
Required evidence:
- File or line evidence of high branching or nesting in one owner.
- Evidence that the complexity is caused by mixed responsibilities rather than by one cohesive stable control role.
Negative match:
- Explicit parser, dispatcher, or state-machine owners with one clear stable control responsibility.
- Boundary-process owners whose complexity comes from one well-defined external contract.
Competing cards:
- Prefer `BOOK-02` when the main defect spans several owners and the whole flow is tangled.
- Prefer `BOOK-01` when the main defect is concentrated responsibility rather than overloaded decision structure.
Scope expansion:
- Inspect caller and callee owners around the complex control flow.
- Inspect whether decisions can be partitioned by concern, collaborator, or boundary role.
Refactor direction:
- Split the flow by decision family or stable collaborator responsibility.
- Push policy decisions into narrower stable owners.
Exceptions:
- Explicit parsers, dispatchers, or state machines with one clear stable semantic role.

### PRJ-17 Dependency Fan-Out Beyond Owner Role
Positive match:
- One owner coordinates too many unrelated dependencies for its stable role.
- The dependency surface spans several unrelated boundary or domain roles without a valid carveout.
Required evidence:
- File or line evidence of broad dependency fan-out in constructor args, stored fields, or imports.
- Evidence that the same owner role does not justify that dependency breadth.
Negative match:
- Explicit `composition root` owners.
- Stable boundary translators or gateway aggregators whose role is to coordinate one boundary family.
Competing cards:
- Prefer `PRJ-01` when the overloaded owner is the `composition root` and also contains business logic.
- Prefer `PRJ-03` when the main defect is hidden local construction instead of fan-out breadth.
- Prefer `BOOK-01` when fan-out is part of one larger dominant-owner problem.
Scope expansion:
- Inspect constructor args, stored dependency fields, and imported boundary owners together.
- Inspect whether some dependencies should move into narrower collaborators.
Refactor direction:
- Split the owner or move dependencies into narrower stable collaborators.
- Keep dependency surfaces aligned with one stable owner role.
Exceptions:
- Explicit `composition root` owners.
- Stable boundary translators or gateway aggregators with one clear boundary role.
