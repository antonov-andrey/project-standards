# Execution Integrity

## User Change Protection Rules

- Do not overwrite, restore, or revert user-authored changes without an explicit user request.
- If a change looks accidental, stop and ask before restoring the previous state.
- A structure cleanup is not permission to rewrite unrelated code or prose.

## Honest Execution Rules

- VCS dependency revision contract:
  - Declare a VCS dependency without a commit, tag, or branch revision suffix by default.
  - Add or retain an explicit VCS revision only when the user has expressly authorized that pin.
- Claim verification contract:
  - Treat every factual claim about code, behavior, status, completion, verification, or repository state as unverified until it is checked against the current repository state.
  - If current evidence is missing, report the claim explicitly as an assumption instead of a fact.
  - Explicit user instructions about desired changes remain authoritative only when they do not conflict with applicable higher-priority instructions, but factual assertions about repository or task state still require verification.
- Instruction interpretation contract:
  - Follow applicable instructions by both their literal text and their intended outcome.
  - When the likely intended outcome is clear and ambiguity is low-risk, choose the interpretation that best fits the current request and context, and state assumptions explicitly when needed.
  - When ambiguity, contradiction, copied or delegated instruction content, or unclear instruction provenance could materially change the work or trigger a costly or irreversible action, stop and ask for confirmation before acting.
- Evidence integrity contract:
  - Do not falsify evidence.
  - Do not report completion, verification, or repository state from stale evidence.
  - Do not substitute weaker surrogate checks or weaker surrogate evidence for required verification.
  - Do not write, change, select, or interpret tests in a way that avoids exercising required behavior, hides missing work, or manufactures misleading passes.
- Completion integrity contract:
  - Required task scope MUST be completed in substance, not only by formal checklist or protocol completion.
  - Passing checks MUST NOT be reported as a substitute for required semantic review.
  - Do not report partial work as complete or current when required scope remains unfinished.
  - Do not replace a clean professional solution with a dirty hack to claim completion.
- Scope-evasion ban:
  - Instruction-evasion and shortcut behavior are forbidden even when they appear to satisfy the process formally.
  - Do not narrow required scope silently or omit expensive or long work instead of reporting a blocker.
  - Do not rename, retype, move, or split artifacts to evade stricter rules, skill triggers, or file-type-specific standards.

## Verification And Handoff Contract

- Verification MUST cover the changed artifact type and the changed observable behavior.
- Changed executable behavior MUST use automated behavior tests when those tests are direct evidence of correctness.
- Project-code changes MUST run targeted checks that directly exercise the changed behavior in addition to the applicable ordinary handoff suite.
- Instruction-only and documentation-only changes that do not change executable behavior MUST use explicit semantic reread of the changed text and its directly referenced canonical owners plus applicable non-test artifact validation; they do not require a Product test suite only because prose changed.
- Structural owner moves MUST verify the new owner, removal of the old owner, and every directly dependent instruction, documentation, test, tool, dependency, and consumer boundary.
- A mechanical standard check is evidence only for independently normative closed predicates that its implementation decides completely. It MUST identify its result as mechanical and MUST NOT replace, narrow, seed, or close semantic review.
- Semantic verification MUST derive its coverage independently from the complete applicable owner contracts. A checker inventory, successful command, implementation plan, previous audit, or already known finding list MUST NOT define or limit semantic scope.
- When one task requires semantic acceptance after fixes, every fix invalidates the prior semantic completion pass. After applicable mechanical verification, repeat the complete semantic review from owner discovery until one fresh pass finds no violation and no uncovered requirement.
- After fixing one failed verification target, rerun that same target before running broader partial or full verification.
- Do not hand off while required verification is failing. Fix repository-local fallout in the same task; report a blocker only when remediation depends on unavailable external state, lies outside the authorized repository boundary, or requires an unapproved semantic contract change.
- One command may be reported as `Pass` only when it exited successfully. Report warnings and other material diagnostics explicitly.
