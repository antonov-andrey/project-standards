# Python Naming Contract

## Table Of Contents

- [Applicability](#applicability)
- [Public Naming Structure And Reuse](#public-naming-structure-and-reuse)
- [Script Filename Rules](#script-filename-rules)
- [Function And Method Naming](#function-and-method-naming)
- [Cross-Layer And Public Model Naming](#cross-layer-and-public-model-naming)

## Applicability

These rules extend identifiers whose defining declarations live in non-`Legacy`, non-test Python code.

- `phrase core-first order`: in any owner-controlled semantic phrase, the leftmost token MUST be that phrase's most general stable core term, and tokens to the right MAY only narrow or qualify it. Tokens whose positions are fixed by another naming rule, such as owner or boundary prefixes, boolean prefixes, `from`, `by`, collection suffixes, and numeric suffixes, keep their rule-owned positions.

## Public Naming Structure And Reuse

- Stable core object names MUST stay contiguous.
- Serialization or data-format qualifiers such as `Json`, `Yaml`, or `Csv` MUST NOT split one stable core object name; place those qualifiers immediately after the stable core object name and before the broader owner noun, for example `OfferTypeJsonConfigLoader`.
- Framework or storage-binding qualifiers such as `SqlAlchemy` MUST NOT split one stable core object name; place those qualifiers immediately before that stable core object name, for example `SqlAlchemyParsedOfferTypeRepository`.
- External integration, cache-provider, or runtime-boundary qualifiers such as `OpenaiCached`, `Playwright`, `Cli`, and `Api` MUST prefix the stable core object name, for example `OpenaiCachedTranslationService` and `PlaywrightCategoryCollector`.
- Execution-mode qualifiers such as `Sync` and `Async` MUST suffix the stable core object name or the already-qualified boundary stem, for example `PromptAsync` and `OpenaiCachedPromptAsync`.
- Before introducing one new public class or public model in non-`Legacy` code, inspect the nearest analogous non-`Legacy` cases in the governed repository and reuse their naming pattern. Priority order:
  - the same owner family,
  - the same runtime role,
  - the same boundary type.
- A new public noun is allowed only when no suitable non-`Legacy` analogy exists at that priority order.
- Tokens such as `all`, `one`, `any`, `first`, `last`, `default`, `changed`, and `explicit` are variant or selection modifiers rather than object nouns.
- Variant or selection modifiers MUST be omitted when the same owner scope has no contrasting variant that requires that distinction.
- When an external API, CLI, protocol, framework, or ecosystem convention already owns a name, keep that convention at the narrowest owning boundary instead of spreading it into cross-layer contracts.

## Script Filename Rules

- `Python script` filenames MUST use `snake_case`.
- `Python script` filenames MAY start with one standard prefix `util_` or `test_`.
- `Python script` filenames MUST use token order `object ... action` after removing one allowed standard prefix when it is present.

## Function And Method Naming

- Function and method names MUST follow this token-order contract:
  - `self-method receiver omission`: if a method name under any template in this section would use the receiver noun as `{object}`, the method MUST omit that receiver noun and use the receiver-owned form instead, for example `{action}`, `{action}_{modifiers}`, `validate`, `validate_{modifiers}`, `is_ok`, or `is_ok_{modifiers}`.
  - `functions require object phrase`: plain functions MUST NOT use `{action}` or `{action}_{modifiers}` without an object phrase.
  - `tool` entrypoint exception: in changed scope, a direct-execution `tool` `Python script` entrypoint function MUST be named exactly `main`.
  - `tool` parse-helper exception: when a changed direct-execution `tool` `Python script` uses a dedicated CLI argument-parsing helper, that helper MUST be named `args_parse` or `_args_parse`.
  - `bool_prefix`: function and method names that return `bool` MUST use one left-edge boolean prefix form; postfix boolean forms such as `filename_log_is` are forbidden.
  - Allowed boolean prefix forms:
    - `is_{object_or_state}`
    - `have_{object}`
    - `can_{action}`
    - `should_{action}`
    - `must_{action}`
    - `need_{object}` or `need_{action}`
    - `support_{object}` or `support_{action}`
    - `match_{pattern_or_object}` for conformance, equality, or compatibility checks against a pattern or another object
    - `contain_{object}`
    - `exist_{object}` for existence, presence, or availability checks; do not use it for receiver-owned possession where `have_{object}` is the correct form
  - `tuple` carrier ban: functions and methods MUST NOT use `tuple` as one business-data carrier in returns or implementation-local state; variable-length homogeneous results MUST use the canonical collection carrier, and fixed-shape results MUST use one explicit object or be split into sequential named operations instead of one tuple; hardcoded immutable constant data MAY still use `tuple`.
  - `collection object phrase`: when one object phrase inside one function or method name denotes one owner-controlled collection carrier, that phrase MUST use the canonical collection suffix required by `Cross-Layer And Public Model Naming`; query methods that return such a carrier MUST still use `{object_phrase}_get`, for example `{object}_list_get`, `{value_object}_by_{key_object}_map_get`, or `{object}_set_get`; bare plural collection phrases such as `offer_types_append` are forbidden when the carrier is one `list[...]`.
  - `_count object phrase`: when a function or method name uses `_count`, the token immediately before `_count` MUST be singular.
  - `{object}_get`: query functions and methods whose primary purpose for the caller is to return one object phrase through real lookup, translation, computation, or other non-trivial retrieval work MUST use that form; trivial proxy accessors that only expose an already available field are forbidden.
  - `non-query returned value`: functions and methods whose primary purpose is command, workflow, lifecycle, or resource action MUST NOT use `{object}_get` only because they return one value as a secondary result.
  - `{object}_validate`: functions and methods that validate one object and fail by raising an exception on invalid state MUST use that form.
  - `is_{object}_ok`: functions and methods that return `bool` for one object's validity, health, or acceptability MUST use that form.
  - `{object}_{error}_list`: functions and methods that return collected errors MUST use that form; `{error}` MUST name the concrete error kind or error type, depending on context.
  - `composite returned object`: when a function or method returns one named aggregate such as `{...}_by_{...}_map`, `{...}_index`, `{...}_context`, `{...}_scope`, `{...}_report`, `{...}_result`, `{...}_config`, or `{...}_state`, that aggregate name MUST be the object phrase of the function or method name.
  - `{object}_{action}`: otherwise function and method names MUST use that form.
  - `composite action phrase`: `{action}` MAY itself use multiple tokens when needed, for example `mark_active` or `save_and_close`.
  - `alternate constructors`: non-default constructor methods are a special case. When the receiver already provides the returned-object context, alternate constructor methods MUST use the `from_` prefix and the full name MUST be `from_{source_or_variant}` or `_from_{source_or_variant}`. `{source_or_variant}` MUST name the source, input form, or variant from which the returned object is built.

## Cross-Layer And Public Model Naming

- Corresponding stable entities across code, storage, docs, CLI, and other owner artifacts MUST keep the same stable core name or use one transparent rule-owned name mapping; ad hoc divergent renames are forbidden.
- One project-local semantic entity across owner-controlled classes, fields, functions, methods, modules, docs, CLI, and other owner artifacts MUST keep one canonical stable name while that entity's semantics stay the same.
- If corresponding stable entities need different layer-local name shapes, that transition MUST be deterministic and obvious from one explicit owner rule, for example by case normalization or one standardized suffix, rather than by arbitrary word substitution.
- In owner-controlled code, one stable entity or collection carrier name MUST use one singular core noun.
- Owner-controlled representations of one class or ORM model MUST use the same field names as that canonical class or ORM model.
- Such owner-controlled representations MAY omit fields but MUST NOT rename semantically identical fields.
- Field renaming is allowed only at one explicit external boundary when an external contract requires that naming, and that mapping MUST stay boundary-local instead of spreading inward through project-local layers.
- `typed suffix or carrier optional form`: when one suffix or carrier-form rule in this section requires one base type or carrier shape `T`, that rule means `T` in the base case and MAY also use `T | None` when `None` means no data.
- Temporal naming prefix semantics:
  - `t_{event_or_state}` means the timestamp when that event or state happened and MUST use type `datetime`.
  - `t_create_{object_or_state}` means the timestamp when that object or state was created and MUST use type `datetime`.
  - `t_update_{object_or_state}` means the timestamp when that object or state was updated and MUST use type `datetime`.
- Numeric naming suffix semantics:
  - Allowed int suffix forms:
    - `_count` means quantity or cardinality, is the canonical project-local suffix for counts, and MUST use type `int`.
    - `_number` means one identifier, ordinal, label number, or other non-count numeric designation such as one vehicle or route number, MUST use type `int`, and MUST NOT be used for count semantics in project-local names.
    - `_index` means one positional index in one ordered sequence and MUST use type `int`.
- In owner-controlled code, any stable name for one `list[...]`, `dict[...]`, or `set[...]` carrier, including typed class fields, typed function or method parameters, and collection object phrases inside function or method names, MUST use one stable form that matches the real carrier shape:
  - `..._list` for `list[...]`,
  - `..._by_..._map` for `dict[...]`,
  - `..._set` for `set[...]`.
- For one `..._by_..._map` name, both phrases around `_by_` MUST be the same standalone variable-style object phrases that would be used for one mapped value and one lookup input outside the map itself; meta wrappers such as `value` before `_by_` and `key` before `_map` are forbidden.
- This singular-core-noun plus carrier-suffix rule applies to stable names in class fields, ORM fields, function and method parameters, local variables, and collection object phrases inside function and method names.
- Bare plural carrier names such as `items`, `rows`, `tables`, `values`, or `prices` are forbidden in owner-controlled code when the same meaning is one singular core noun plus the canonical carrier suffix.
- A singular word that happens to end with `s` is allowed and is not by itself a plural-form violation.
- A singular domain, product, platform, protocol, or external-boundary token that ends with `s` MUST NOT be renamed merely because its spelling resembles a plural. Determining that semantics belongs to semantic review and MUST NOT be approximated by a plural-token checker or checker exception list.
- One such collection name MUST keep the same suffix across adjacent owner-controlled layers and across function or method names that refer to that same carrier while the carrier shape stays the same; for example do not rename one owner-local `candidate_list` into `candidates` at a local prompt or payload contract boundary, and do not name one method `candidates_append` when it appends to `candidate_list`.
- This collection-suffix rule does not apply when an external API, protocol, framework, persisted schema, or other externally owned boundary already fixes a different collection name; keep that external name at the narrowest owning boundary instead of spreading it further inward.
- Public cross-layer model names MUST be owner-coupled:
  - model names MUST start with the same domain, use-case, operation, or boundary stem as the owner that creates, returns, persists, or hands them across a stable boundary,
  - free-floating model names that omit their owning stem are forbidden for public cross-layer models.
- Public cross-layer model naming contract:
  - suffixless model names are allowed when the model's stable role is a domain entity, domain value object, or other domain concept rather than one of the standardized suffix roles below,
  - when a model has one of the standardized semantic roles below, its name MUST use the matching suffix instead of a synonym or alternate suffix,
  - the standardized suffix list below is not exhaustive for every possible semantic role,
  - boundary suffixes such as `Request` and `Response` apply only when the model itself is the stable boundary payload or boundary contract for that integration-facing role.
- Standardized public cross-layer model suffix roles:
  - `Config`: input configuration models.
  - `Request`: external-integration request models.
  - `Response`: external-integration response models.
  - `Result`: operation return models. If multiple return models exist in one scope, distinguish them with owner or phase qualifiers before `Result` instead of inventing another suffix.
  - `State`: state-container or mutable workflow-state models.
  - `Stats`: counter or metric models.
  - `Summary`: outer-boundary reporting-view models.
