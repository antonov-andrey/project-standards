# Python Core Contract

## Applicability

- Unless one narrower code section explicitly says otherwise, these rules apply only to non-`Legacy` code.
- `Legacy` code is outside repository-wide non-`Legacy` structural retrofits by default.
- In `Legacy`, keep behavior working and use idiomatic professional solutions inside the existing owner boundary.

## General Code Rules

- Non-idiomatic or surprising code is forbidden by default.
- If a non-idiomatic construct seems necessary, stop and get explicit user confirmation before adding it.
- Code MUST stay compact and MUST NOT introduce standalone helper functions, local helper callables, or equivalent wrapper artifacts when the same behavior is expressed clearly by one canonical built-in callable, one direct expression, or one trivial inline `lambda`.
- Named helper functions are allowed only when they add real reused value, one real domain name, or one non-trivial algorithm or boundary; one-off wrappers that only restate one trivial built-in callable or one trivial expression are forbidden.
- Top-level functions and methods MUST NOT exist only to proxy unchanged arguments into another callable; code MUST call the real owner directly unless that wrapper adds real behavior or defines one real public boundary.
- Settings, attributes, parameters, fields, and configuration knobs MUST exist only when they express one current required behavior or stable contract; future-use, mirror-only, pass-through-only, and compatibility-only knobs are forbidden.

## Formatting And Docstring Rules

- Every file in non-`Legacy` `Python code` MUST comply with the canonical Black formatting and docstring standard.
- When a change set touches a file in non-`Legacy` `Python code`, that same change set MUST bring that file into compliance with the canonical Black formatting and docstring standard.
- Files in non-`Legacy` `Python code` MUST be formatted with Black using the canonical repository settings `--target-version py314` and `--line-length 120`.
- Files in non-`Legacy` `Python code` MUST have:
  - a module docstring,
  - a docstring on every `class`,
  - a docstring on every `def` and `async def`.
- Covered docstrings MUST:
  - use strict Google-style formatting,
  - include `Args:` when parameters other than `self` or `cls` exist,
  - include `Returns:` when the return annotation exists and is not `None`,
  - stay single-line only when no structured sections are required,
  - become multi-line when `Args:`, `Returns:`, or `Raises:` sections are present,
  - keep one blank line between the summary and the first structured section,
  - keep section headers at base indentation,
  - indent section-item lines by exactly four spaces from base indentation,
  - keep exactly one blank line between the docstring block and the executable body.
- Docstring summaries MUST describe real behavior rather than restating a symbol name.
- Placeholder docstring summaries are forbidden.
- `Args:` sections MUST NOT contain stale entries that are absent in the current signature.
- Do not collapse a naturally multi-line docstring to one line only to satisfy line budgets or line-length pressure.
- Do not change runtime behavior only to satisfy docstring checks.
- During refactor or move, docstrings MUST be preserved and updated with signature changes.

## Multiline String Placement Contract

- Outside one docstring, one static multi-line string payload MUST be defined once as one module-level triple-quoted constant or module variable; local line-sequence builders, string-literal joins, and concatenation chains are forbidden.

## Method Binding Contract

- One callable MUST choose its real owner and binding shape before choosing public or private visibility.
- One callable that uses instance state, permitted instance mutation, or instance-level polymorphic dispatch MUST be an instance method.
- Outside one inherited, protocol-owned, or framework-owned exact-shape contract, `@classmethod` is allowed only for one alternative constructor.
- Within one Python package rooted at `lib/<package>/` or `script/<package>/`, one module-level function or non-instance method MUST NOT return one package-local object; such behavior MUST be implemented either as an alternate constructor on the returned class or as an instance method on one of the package-local object parameters that is the real receiver of that behavior.
- Within one Python package rooted at `lib/<package>/` or `script/<package>/`, one module-level function or non-instance method whose first explicit parameter is one package-local object MUST be an instance method on that parameter's class.
- One callable that uses neither `self` nor `cls` is receiverless logic and MUST be a module-level function.
- `@staticmethod` is forbidden unless an inherited, protocol-owned, or framework-owned contract explicitly requires that exact method shape.
- Same-class dispatch through `self` or `cls` is forbidden when it exists only to reach receiverless helper logic.
- When a real class-level polymorphic contract requires same-class dispatch from a `@classmethod`, that dispatch MUST go through `cls`, not through the hardcoded class name.

## Signature Type Contract

- Function and method signatures MUST NOT use union types except `T | None`.
- One function or method signature MUST model one canonical runtime contract per parameter and per return value.
- The annotated type MUST be the narrowest truthful type that matches the operations actually used by the implementation.
- It is forbidden to widen one signature to `Any`, `object`, one broad base class, or one broader collection interface only to avoid one non-optional union or to satisfy one mechanical checker.
- When one external or framework boundary is initially multi-shape, code MUST normalize it at that boundary into one canonical typed contract instead of leaking non-optional union types through later signatures.
- If code uses one concrete container contract, annotate that concrete container contract.
  - `list[...]` only when the implementation relies on list semantics such as mutation, indexing, slicing, order-sensitive in-place updates, or list-only methods.
  - `dict[...]` only when the implementation relies on dict semantics such as mutation, key insertion/removal, or dict-only methods.
  - `set[...]` only when the implementation relies on set mutation or set-only operations.
- If code uses only one abstract collection interface, annotate that abstract interface instead of one concrete container.
  - `Sequence[...]` only when the implementation needs ordered read-only access.
  - `Mapping[...]` only when the implementation needs read-only key/value lookup.
  - `Iterable[...]` only when the implementation needs iteration only.
  - `Collection[...]` only when the implementation needs membership or length but not indexing or mutation.
- If one parameter annotation is abstract, the implementation MUST NOT use behavior outside that abstract interface.
- Type-driven adaptation branches inside core code are forbidden when they exist only to support multiple input shapes for the same semantic value.
- Internal code that works with filesystem paths MUST use `Path` as the canonical in-repository contract; string paths are allowed only at explicit CLI or external-text boundaries and MUST be normalized there immediately.

## Import Form Contract

- Project-local Python symbols MUST be brought into scope only through canonical `import ...` or `from ... import ...` statements.
- Python imports MUST appear only at module scope.
- Module dependency cycles are forbidden.
- When one cycle appears, code MUST fix owner placement or dependency direction so that shared contracts live under one non-cyclic owner instead of preserving the cycle through local-import workarounds, reverse rebuild hooks from the wrong side, or contract-widening fallbacks.
- Function-local, method-local, nested-scope, and other non-module imports are forbidden.
- Exception: a package module file at `<package>/__init__.py` MAY use non-module imports inside `__getattr__` only for the standard lazy-export pattern that returns one requested package symbol from that same package surface.
- Cross-module imports and cross-module attribute access MUST use only public names, except that `test` code MAY import and access public and private names within its allowed import scope.
- Code MUST NOT use import fallbacks, sentinel assignments, lazy dependency loading, or similar techniques that defer a missing dependency failure from module import or process startup to a later runtime call path.
- When code depends on an importable Python package or module, that dependency MUST be imported eagerly at module scope so missing dependencies fail during startup.
- When code passes or stores one project-local callable, that callable MUST come from such a canonical import binding.
- Dynamic repository-local symbol resolution is forbidden, including `importlib.import_module(...)`, `__import__(...)`, string-based `module:callable_path` resolution, and `globals()`, `locals()`, `vars()`, `sys.modules`, or `getattr()` chains used instead of canonical imports.
- When the governed project instructions explicitly declare one import registry or re-export surface for a symbol family, imports MUST use that canonical surface; otherwise imports MUST use the symbol's defining module.
- Alternative repository-local import paths to the same symbol are forbidden.
- non-`Legacy` non-`test` `Python code` MUST NOT import `Legacy` code.

## Validated Object Contract

- Detached non-ORM contract objects that carry stable field-like data across one boundary or stable handoff, and non-ORM classes that expose stable field-like stored data through their public API, including direct attributes, `property`, getter/setter methods, or `dump`/`snapshot`/`export`-style accessors, MUST inherit from `BaseModelStrict`.
- Plain non-ORM classes are allowed only when their public API is behavior-oriented and does not expose stable field-like stored data.
- `property`, getter/setter methods, and other field-like access paths MUST NOT be used to bypass that requirement.
- `BaseModelStrict` MUST use only standard `Pydantic BaseModel` runtime semantics with `strict=True`, `validate_assignment=True`, `validate_default=True`, and `extra="forbid"`.
- `BaseModelStrict` MUST NOT add mutation-wrapper layers, post-init rewrap, or other extra runtime instrumentation beyond standard Pydantic validation semantics, except for one explicit repository-wide copy-with-overrides path that preserves normal constructor validation.
- `BaseModelStrict` runtime object construction MUST NOT use `model_construct()`.
- `BaseModelStrict.model_dump(mode="python")` is the canonical plain field-dump path for validated detached objects.
- Copying one validated object with canonical field overrides MUST preserve normal constructor validation, and changed canonical field values MUST be rebuilt through the model constructor or one approved owner-defined copy path that itself rebuilds through the model constructor.
- System class attributes on `BaseModelStrict` and row `OrmBase` classes, including `model_config` and ORM class-level metadata such as `__tablename__` or `__table_args__`, MUST be declared before the first field declaration.
- Constructor call sites, alternate constructors, and other approved construction paths for validated objects MUST NOT pre-coerce values, prefill hidden defaults, or apply hidden pre-validation normalization.
- Standard validated-object construction MUST reject incompatible types instead of accepting caller-side type conversion wrappers.
- Helper code around validated-object construction MUST NOT hide fallback defaults or hidden normalization as a compatibility layer.
- Type, default or default factory, field-level normalizer, and field-level value constraints for one validated-object field MUST live in that field's canonical field contract.
- Field-level value constraints include enum membership, length, range, nullability, and shape rules when those constraints are required for that field.
- Constructors, alternative constructors, call sites, exporters, readers, and other surrounding helper paths MUST treat canonical fields as already-final values and MUST NOT re-declare, re-normalize, re-default, or otherwise duplicate field-level typing, defaulting, normalization, or value-shape rules outside the canonical field contract.
- Classes on `BaseModelStrict` MUST expose field-like state directly through their canonical fields instead of getter/setter wrappers, field-mirroring `property` wrappers, or equivalent accessor methods such as `*_get()`, `get_*()`, `*_set()`, or `set_*()`.
- Validated objects MUST treat canonical fields as final typed values immediately after construction.
- Consumer code MUST NOT apply `int(...)`, `str(...)`, `float(...)`, `bool(...)`, `list(...)`, or `dict(...)` to canonical field values only to make them usable.
- Consumer code MUST NOT apply fallback-default logic such as `value or ""`, `value or 0`, `value or []`, or `value or {}` to canonical field values.
- Consumer code MUST NOT apply late normalization to canonical field values.
- If one caller needs more than one semantic representation of one value, those representations MUST live in separate explicit fields instead of one overloaded canonical field.
- Numeric canonical fields MUST use `None` only when nullability is semantically required and `0` is one real in-domain value.
- When one numeric field uses `0` to represent one out-of-domain state such as `not computed`, `missing`, or `not applicable`, that field MUST stay non-nullable and MUST encode that state with canonical `0` instead of `None`.
- Raw companion fields are optional and MAY exist only when owner semantics require preserving raw external input.
- Canonical fields and raw companion fields MUST remain semantically distinct, and raw-value retention MUST NOT justify ambiguous, weakly typed, or partially normalized canonical fields.
- Field-level `default_factory` on validated objects MUST use one no-arg-invocable callable.
- If one canonical built-in callable expresses the required field-level `default_factory` or field-level normalizer on one validated object, that built-in callable MUST be used directly.
- If no canonical built-in callable expresses the required field-level `default_factory` or field-level normalizer on one validated object but the callable stays trivial and one-off, inline `lambda` SHOULD be used.
- Bypass paths around canonical validated-object construction and assignment are forbidden, including helper builders or secondary constructors that silently weaken field validation and ad-hoc mutation paths that assign raw values outside standard assignment validation.

## Class Necessity Contract

- Classes are allowed only when at least one of these holds:
  - the class has stable instance state or invariants that multiple methods read or maintain,
  - the class has a real lifecycle whose steps depend on owned instance state,
  - the class provides a real polymorphic, inherited, or framework-required type contract,
  - the class is a real long-lived boundary whose behavior must stay coupled to owned dependencies or owned state.
- Otherwise use module-level functions.

## Architecture Defaults

- Code in this section MUST use classical OOP as the default design style.
- Objects in this section MUST own their stable behavior close to their stable state and invariants instead of splitting behavior into detached transaction-script helpers.
- Runtime orchestration code in this section MUST use explicit dependency injection for external dependencies and MUST NOT construct them ad hoc inside methods.
- Constructor-first state is mandatory:
  - validate and normalize instance fields in `__init__`,
  - do not use lazy field-check wrappers in hot paths.
- Instance state is immutable by default after initialization.
- Mutability is allowed only for explicit runtime buffers, queues, caches, or lifecycle markers.
- Methods MUST treat instance state as the default source of truth instead of mirroring instance state through mandatory parameters.
- `Stored-state contract:`
  - Every stored instance field MUST have one current stable runtime role.
  - Write-only, symmetry-only, placeholder, or future-use instance fields are forbidden.
  - When an owner has no stable instance state, keep it stateless instead of storing dead configuration or boundary objects.
- Method names inside `*Sync` and `*Async` classes MUST stay mode-neutral.
- Inheritance is the default abstraction-refinement mechanism when a real `is-a` relationship and real shared behavior exist.
- Composition MUST be used when inheritance would create a fake hierarchy or when there is no natural `is-a` relationship.
- Multiple inheritance and mixin pyramids are forbidden.

## Structure And Logic Placement Defaults

- Code in this section MUST prefer clear domain classes and modules over ceremonial layering.
- New code in this section MUST start from direct domain classes and modules that each own substantial behavior.
- Helper-heavy decomposition is forbidden by default.
- For script-like and process-like code in this section, the default structure is:
  - one top-level function that owns the full run when no stable instance state is needed; otherwise one top-level class that owns the full run,
  - one workflow class when the run is one bounded multi-step contract whose correctness depends on ordered steps, cross-step handoff, lifecycle boundaries, or side-effect sequencing; size alone is not a sufficient criterion,
  - concrete service, repository, parser, or integration classes only when they own substantial behavior or a real external boundary.
- Module and package structure MUST follow domain concepts or stable technical roles instead of fragmented generic buckets.
- Code duplication is forbidden; repeated behavior MUST have one shared implementation place.
- Base classes MUST contain real shared behavior rather than only signatures.
- Local parsing, normalization, retry, merge, payload-build, and selection logic MUST stay as methods on the class that uses that logic unless the code is reused across multiple stable classes or is a real external integration.
- Reusable mechanics that serve more than one stable caller MUST move to the lowest reusable owner that already owns that concern.
- Data-only containers are allowed only at explicit boundaries and MUST NOT become detached repositories of business meaning.

## Helper Artifact Restrictions

- Single-use modules, standalone functions, helper-only modules, and helper-only classes are forbidden by default.
- They are allowed only when they own a real invariant, a real boundary or external integration, a non-trivial reusable algorithm, or the top-level run of one script-like or process-like flow allowed by `Class Necessity Contract`.

## Top-Level Run-Flow Ownership

- The full top-level run flow includes:
  - parsed-CLI to config translation,
  - bootstrap and readiness calls,
  - dependency wiring,
  - top-level workflow invocation,
  - final run-summary reporting.
- If a script needs the run timestamp, compute it exactly once in the owner of the top-level run flow and pass it downstream as a value.
- The full top-level run flow MUST remain contiguous inside its owner.
- Do not split one top-level run across extra wrapper classes, free-function orchestration fragments, or helper-only stage routers unless that code is real reusable code or a real external integration.

## Python File Layout Contract

- Module-level file structure is mandatory and MUST follow this exact order:
  - import groups,
  - constants,
  - module variables,
  - public functions,
  - class blocks.
- Import groups MUST appear in this exact order:
  - Python standard-library imports,
  - third-party Python imports,
  - repository-local imports, including root-repository code and `Submodule` packages.
- Import groups MUST be separated by exactly one blank line.
- Within each import group, import statements MUST be sorted alphabetically by imported module path.
- Within one `from ... import ...` statement, imported names MUST be sorted alphabetically.
- Constants MUST be module-level names whose canonical role is constant data, they MUST follow the dependency-aware alphabetical rule in this contract, and one contiguous constants block MUST NOT contain blank lines between adjacent constant items.
- Module variables MUST be module-level non-constant data names, they MUST follow the dependency-aware alphabetical rule in this contract, and one contiguous module-variable block MUST NOT contain blank lines between adjacent module-variable items.
- When one constants block is immediately followed by one module-variable block, those two blocks MUST be separated by exactly one blank line.
- Public functions MUST follow the dependency-aware alphabetical rule in this contract.
- Class blocks MUST follow the dependency-aware alphabetical rule in this contract.
- Within one same-kind block of constants, module variables, public functions, or class blocks, alphabetical order by identifier name is mandatory by default.
- One identifier MAY appear earlier than its alphabetical position only when one direct eager runtime dependency requires that identifier to be bound earlier during import-time evaluation.
- One direct eager runtime dependency means one dependency used by one base-class expression, one decorator, one default-value or default-factory expression, or one other module-level or class-definition expression evaluated while the module imports; references that exist only inside one later-executed function or method body do not justify breaking alphabetical order.
- When one identifier uses this exception, that identifier MUST be placed at the latest file position that still leaves every such direct eager consumer valid.
- When more than one same-kind identifier must be placed earlier for the same later consumer, that dependency-driven earlier block MUST stay alphabetically sorted internally unless one identifier in that same block has its own direct eager runtime dependency on another identifier in that same block.
- For one class block, every private module-level function used only by that class MUST be placed immediately before that class and those private functions MUST follow the same dependency-aware alphabetical rule in their helper block.
- A private module-level function used only by one public function MUST be placed immediately before that public function and MUST follow the same dependency-aware alphabetical rule in its helper block.
- A private module-level function used by more than one public function or class in the same file MUST be placed immediately before the first consumer in the required file order, and that helper block MUST follow the same dependency-aware alphabetical rule.
- When code changes make this required file placement point to a different location inside the file, the implementation MUST be moved in the same change instead of preserving the old placement.
