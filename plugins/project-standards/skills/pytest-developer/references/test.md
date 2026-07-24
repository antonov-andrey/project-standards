# Pytest Contract

- Python tests use `pytest`.
- Root pytest is the canonical repository suite and discovers owner-local test roots through the repository's declared configuration.
- `Submodule` tests remain runnable both standalone and through a consuming repository when that repository includes them in its suite.
- Behavior tests live in the owner-local test placement selected by the project; slower or environment-dependent tests are separated explicitly.
- Test support code remains owner-local. `conftest.py` contains only shared fixtures, hooks, marker or configuration registration, and private helpers used only there.
- Tests do not depend on execution order, production services, wall-clock timing, or shared mutable global state.
- Tests do not assert exact instruction prose, headings, examples, or file presence as a proxy for semantic synchronization.
- Changed behavior covers success, its primary contract-defining failure, and every critical introduced branch.
- A failure is inspected through the failing test body, its fixtures and owner-local helpers before production behavior or expectations are changed.
