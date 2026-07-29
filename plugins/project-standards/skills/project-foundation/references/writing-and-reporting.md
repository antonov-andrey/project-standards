# Writing And Reporting

## Writing Rules

- `Writing Rules` own the repository-wide prose, readability, and list-structure baseline.
- Structure contract:
  - Use paragraphs when the content is explanatory and not inherently list-shaped.
  - Use bullets or numbered lists only when the content is genuinely list-shaped and entries benefit from explicit separation.
  - When one bullet-based section states rules, facts, or observations for multiple entities or targets, sibling bullets about the same entity or the same explicit parent predicate MUST stay adjacent.
  - When several sibling bullets belong to the same entity or the same explicit parent predicate, they MUST use one parent bullet with grouped sub-bullets instead of a longer flat list unless that grouping would hide different owner sections.
  - When sibling bullets share a repeated textual prefix, a repeated textual suffix, or the same explicit parent predicate, that shared text MUST move into the parent bullet and child bullets MUST keep only the distinct peer items.
  - One idea MUST NOT be split across a parent bullet and a one-child sub-bullet chain when no real enumeration, exception set, or distinct predicate exists; write that case as one bullet instead.
  - When one list expresses a peer set, render that set vertically instead of as one inline horizontal enumeration.
- Readability contract:
  - Prose MUST stay direct, explicit, and easy to scan for its intended audience.
  - The term `repository-owned` is forbidden in instruction artifacts because it is ambiguous about ownership versus git state; use `project-local` terms or explicit path-scoped wording instead.
  - Avoid filler, congratulatory framing, and meta commentary that does not change the meaning.
  - Prose MUST NOT use width-driven hard wrapping.
  - Keep each paragraph and each bullet text block on one physical line unless the surrounding structure requires separate lines.
  - Preserve template-owned literal headings and labels exactly when a canonical template owner requires them.

## Language Zones

- English-language contract:
  - When an applicable rule requires English, use ASD-STE100 Simplified Technical English, Issue 9, dated 2025-01-15.
  - Use only the words, meanings, parts of speech, and verb forms that Issue 9 permits. Use canonical project terms as technical nouns or technical verbs.
  - Use American English spelling. Use active voice. Use the imperative form for instructions.
  - Use no more than 20 words in a procedural sentence and 25 words in a descriptive sentence.
  - Put only one instruction in a sentence. Put only one topic in a paragraph. Use no more than six sentences in a paragraph.
  - Do not use contractions, semicolons, or unapproved phrasal verbs.
  - This contract changes only the form of English. It MUST NOT change the required language, content, meaning, owner, scope, workflow, output structure, or literal text.
- User-facing prose contract:
  - Any prose addressed to the user MUST use the language of the user's current request unless the user explicitly requests another language.
  - If the user's current request mixes multiple natural languages without an explicit language choice, use the dominant language of the user's prose; if that is still unclear, use the language of the most recent explicit user language preference, or otherwise the dominant language of the most recent user prose in the conversation.
  - If an external protocol requires literal wrapper tokens such as `<proposed_plan>` and `</proposed_plan>`, keep only those literal tokens unchanged; all other surrounding and enclosed prose MUST still use the language of the user's current request.
  - User-facing plans, summaries, and explanations MUST NOT switch to English only because repository instruction artifacts or internal contracts are written in English.
- Default non-user-facing prose contract:
  - Unless a more specific applicable owner rule says otherwise, non-user-facing prose MUST use English.
- Documentation prose contract:
  - Prose in `DESIGN.md`, `design/**`, and `docs/**` MUST use Russian and follow `Russian-language artifact contract`.
- Russian-language artifact contract:
  - Russian MAY be required by product contracts for code prompts and user-facing business text.
  - When an applicable owner or product contract requires one artifact to use Russian:
    - keep that artifact's prose in Russian,
    - write named terms and named entities used as named entries in English and in backticks,
    - allow English only for:
      - canonical named terms from this repository or another directly referenced owner contract,
      - literal code identifiers, file paths, command names, CLI flags, API or schema field names, env vars, and other machine-facing tokens,
      - template-owned literal strings required by the canonical template owner,
      - a narrow technical term with no equally precise Russian wording in current repository usage,
    - forbid generic English prose fragments, connective wording, and broad English technical phrasing when a clear Russian formulation exists.
- Template-owned literal strings required by an artifact family's canonical template owner MUST remain in that template-owned language even when the surrounding artifact family uses another language.

## Problem Reporting Rules

- These rules apply when prose describes one or more concrete problems, findings, issues, or blockers.
- Pure questions, clarifying notes, and non-problem remarks are outside this contract.
- Entry separation contract:
  - each described problem entry MUST be clearly separable from other problem entries,
  - one problem entry MUST describe exactly one problem,
  - when one response lists multiple problem entries, each entry MUST be presented as one bullet in the canonical problem-entry shape.
- Problem-entry contract:
  - each described problem entry MUST use exactly this shape:
    - `- <Severity>: <Problem>`
    - `  Fix: <Fix>`
  - `<Severity>` MUST be exactly one of `High`, `Medium`, or `Low`.
  - `<Problem>` MUST be one detailed clear description of the problem.
  - `<Fix>` MUST be one detailed clear description of the fix.
  - `<Fix>` MUST state one unambiguous recommended correction path, including the concrete behavior change and verification target when those details are known.
  - Alternative fixes MAY be mentioned only after the recommended `<Fix>` and MUST NOT replace the single recommended correction path.
  - for one unresolved problem, `<Fix>` MAY be a proposed or required fix instead of an already applied fix.
  - blocker reasons, verification notes, and other context MAY be added only after that canonical two-line shape and MUST NOT replace it.
- Ordering contract:
  - when one response lists multiple problem entries, list them in severity order `High -> Medium -> Low` unless a more specific applicable workflow contract requires a different order.
- Completeness contract:
  - any problem description that does not satisfy the canonical two-line problem-entry shape is forbidden,
  - passing checks, generic reassurance, or generic `needs investigation` wording do not replace a required problem entry when the response is actually describing a current problem.
