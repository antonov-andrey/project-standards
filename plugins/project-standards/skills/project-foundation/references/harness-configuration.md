# Harness Configuration

## Project Harness Configuration Rules

- User-level harness configuration owns personal model, reasoning, feature, approval, sandbox, instruction-size, subagent-topology, and integration defaults shared across projects.
- Project-local harness configuration MAY contain only settings backed by an independent project-specific behavior requirement.
- A value that merely duplicates the current user configuration or a documented harness default without an independent project requirement is forbidden.
- Reusable workflows and domain skills MUST adapt to available harness capabilities and MUST NOT require copied consumer-local model, concurrency, or named-role configuration.
- If no project-specific setting remains, the project-local harness configuration file and its `Key Directory Map` entry MUST be deleted.
