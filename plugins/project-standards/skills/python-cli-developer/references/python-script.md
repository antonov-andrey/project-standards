# Python Script

- `Python script`
  - Meaning: a Python file that is not ignored by `.gitignore` and is intentionally executable from its owning repository boundary by direct relative path.
  - Launch contract: it MUST start with the exact shebang `#!/usr/bin/env python3`, MUST have executable mode `755`, and MUST launch from that owning repository boundary by direct relative path, with an optional `./` prefix allowed.
  - Boundary rule: Python modules that are not ignored by `.gitignore` and are outside intentionally executable entrypoint paths MUST NOT expose direct-execution `__main__` guards.
