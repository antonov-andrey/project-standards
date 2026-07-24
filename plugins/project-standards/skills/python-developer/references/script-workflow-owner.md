# Script Workflow Owner Pattern

## Purpose

This reference describes how to structure one bounded runtime algorithm when it is split into ordered stages. The pattern keeps the whole run under one explicit workflow owner, makes stage order and handoff rules visible, and prevents generic stage buckets, proxy coordinators, and hidden side-effect ownership.

## Applicability

Use this pattern for non-`Legacy` `Main project code` when one bounded algorithm has two or more ordered stages and correctness depends on at least one of these concerns:

- stage order,
- cross-stage data handoff,
- persisted side effects,
- transaction boundaries,
- external resource lifecycle,
- finalization after earlier in-memory work.

Do not use this pattern for one simple operation with no meaningful stage split, for reusable library APIs where the caller owns orchestration, or for long-running worker loops whose runtime is governed by worker-manager contracts.

## Pattern

- One top-level workflow owner owns the complete bounded run from parsed inputs and dependency wiring through final summary or result.
- Stage names must be domain-specific and visible in code. Generic `stage_*`, `step_*`, `phase_*`, coordinator-only, or helper-bucket naming is forbidden when it hides the real owner or real operation.
- The workflow owner may implement a stage as its own method when the stage mainly reads or mutates workflow-local state.
- A separate stage owner is allowed only when it owns exactly one visible stage or one real external boundary used by that stage.
- Separate stage owners must receive minimal explicit inputs and return one explicit result surface. Wide argument packs, anonymous tuple returns, and heterogeneous anonymous dict results are forbidden for cross-stage handoff.
- One workflow must use exactly one cross-stage handoff model:
  - workflow-local `State`, when several stages share mutable run data,
  - direct value/result passing, when handoffs stay narrow.
- Do not mix workflow-local `State` with broad direct relay arguments for the same workflow.
- Workflow-local `State` is run-local mutable data owned by the workflow owner. Immutable config, dependencies, and run metadata stay on the workflow owner, not inside state.
- Persisted side effects must belong to an explicit updater, writer, repository boundary, or another concrete owner that is visible from the workflow. Do not hide final writes inside generic helpers.
- Transaction boundaries must be visible at the workflow level when the bounded run writes through a transactional persistence boundary. Stage owners inside one mapped transaction do not open their own transaction boundaries unless batching, retry isolation, or another correctness constraint requires it.
- Nested stage decomposition is allowed only when the parent stage remains the owner of the outer contract and the child stage order, handoff values, and side-effect owners are named at the parent stage boundary.
- Resource finalization and asynchronous lifecycle boundaries must be as visible as the stages that make them necessary.

## Review Questions

- Can a reviewer name one workflow owner for the whole bounded run?
- Can a reviewer read the ordered stage sequence without reconstructing it from scattered helper calls?
- Does every extracted stage owner own one visible stage or one real external boundary?
- Are cross-stage handoffs explicit, narrow, and represented by one consistent handoff model?
- Are persisted side effects and transaction boundaries owned by visible runtime participants?
- Are names chosen from nearby non-`Legacy` project analogies instead of copied from legacy helper layering?
- If one stage has child stages, are their order, handoffs, and ownership clear without creating a second workflow owner?

- `references/script-workflow-owner.md` owns the reusable implementation pattern for one bounded runtime algorithm split into ordered stages.
- Apply that pattern when non-`Legacy` project code implements a bounded algorithm with two or more ordered stages and its correctness depends on the applicability conditions declared by this reference.
