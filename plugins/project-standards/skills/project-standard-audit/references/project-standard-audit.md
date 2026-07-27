# Project Standard Audit

- Derive semantic scope independently from every current canonical owner, not from checker inventory, checker output, previously noticed concerns, historical findings, or the implementation plan.
- Compare actual project entities and boundaries with the provider-owned triggers of capabilities declared in `Required Standards`.
- Treat every missing applicable capability from another provider as a finding unless an explicit user-authorized exception is present.
- Confirm each provider-qualified skill is installed and discoverable.
- For every declared `project-standards:*` capability, record whether its provider-owned trigger applies and why. For every applicable provider, inspect every normative rule family in the applicable provider references. For every project instruction owner, inspect every normative section, modeled term, dependency boundary, path binding, command, exception, and referenced stable design owner.
- Record one semantic verdict and current evidence for every applicable requirement. Record one explicit reason for every not-applicable requirement. Missing coverage is itself a finding.
- Confirm project-local prose contains concrete paths, runtime versions, commands, side effects, security, verification, and authorized specializations rather than copied provider prose.
- Confirm reusable generic skills and agent support assets exist only in their provider.
- Confirm stable design and maintained docs use their canonical owners.
- Confirm no compatibility document, duplicate harness default, or hidden secondary checkout remains active.
- For protected instruction migrations, validate the complete approved source-to-target ledger in addition to the final semantic model.
- When fixes are authorized, rerun applicable mechanical checks after each fix set, then restart the complete semantic audit from owner discovery. Completion requires one fresh full semantic pass after the last fix with no findings and no uncovered requirement.
