# Behavioral Evaluation Acceptance

One acceptance cycle evaluates a selected behavior corpus on `gpt-5.6-sol` with `reasoning_effort=max`. The runner detects possible failures; the canonical skill, instruction, and scenario contracts determine correctness.

## Convergence Workflow

1. Run every selected case exactly once with `skill_behavior_eval.py`, write its result JSON, and do not retry a case during that pass.
2. Read the exact `failed_case_id_list` from the result. An empty list completes the cycle.
3. For every failed case, compare the generated response and judge decision with the canonical contract before changing anything.
4. Classify each failure as exactly one of:
   - the generated response violates the canonical contract, so fix the owning code, skill, reference, or project instruction;
   - the response is semantically correct, so fix the owning ambiguous scenario, incorrect invariant, activation set, or evaluator instruction.
5. Resolve all failures in the current set in one iteration.
6. Run the next pass with one repeatable `--case <suite-qualified-id>` argument for each ID from the preceding `failed_case_id_list`, using the same model and max effort.
7. Feed the ordered initial and targeted result files to `skill_behavior_acceptance.py --result <path> ...`. Its `next_case_argument_list` contains only the remaining failures. Do not run that next command until every current failure has been classified and its root fixed.
8. Repeat classification, root fixes, and targeted evaluation until `failed_case_id_list` is empty. The first zero-failure result is terminal model-evaluation evidence for the cycle; cases that passed in earlier iterations retain their successful result.

Formally, `S0` is every selected case, `Sn+1 = failed(Sn)`, and the cycle succeeds when `failed(Sn)` is empty. A passed case MUST NOT re-enter the same cycle, and a full corpus pass MUST NOT be repeated to confirm a targeted fix.

## Canonical Classification Rules

- Every invariant checks meaning, is self-contained for the semantic judge, and cites behavior required by the canonical contract.
- Exact words, headings, ordering, or response form are required only when the canonical contract requires that exact form.
- Read-only evaluation simulation judges whether the response commits to the required real mutation; it neither requires nor rewards physically performing that mutation during evaluation.
- `expected_skill_list` and `forbidden_skill_list` describe skills actually activated for the response, not capabilities present in the catalog or merely considered.
- Judge output is diagnostic evidence, not the source of truth. An ambiguous scenario, incorrect invariant, wrong activation set, or unstable judge instruction is fixed in its own canonical corpus or evaluator owner.
- Production instructions and production data change only after confirming that the generated response violates their canonical contract. They MUST NOT be changed to fit one stochastic output.

## Commands

Server bootstrap first installs every exact provider revision required by the selected cases in the current operating-system user's standard Codex home. The initial runner command then supplies every selected corpus, the same exact local plugin marketplace and plugin selector, `--model gpt-5.6-sol`, `--reasoning-effort max`, and one immutable `--output` path. The runner validates that every installed plugin cache is byte-for-byte equal to its declared source and does not install or isolate plugins itself. The standard home, native wait, resume, and exact usage boundaries are owned by `project-standards:project-foundation`, reference `Codex Process State`.

Selection may be the complete corpus or explicit repeated `--case` arguments.

After classifying and fixing every current failure, copy `next_case_argument_list` from the acceptance planner as direct repeated arguments to the same runner command and write a new immutable result path. Replay all result paths in order through the planner. Planner exit `1` means failures remain, exit `0` means the cycle converged, and exit `2` means the result sequence violates the contract.
