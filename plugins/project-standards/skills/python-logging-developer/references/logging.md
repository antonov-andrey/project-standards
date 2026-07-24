# Python Logging Contract

The provider `config_logging/DESIGN.md` owns the logging bootstrap and log-record interface. A project that contains Python logging MUST use that provider contract unless the user explicitly requires a project-local exception.

Logging is initialized exactly once per process at root bootstrap through `config_logging`. A second configuration attempt in the same process is an error. A spawned child process is a distinct process and may perform its own single bootstrap.

After bootstrap, product code uses direct `import logging` module calls. Product code does not create, configure, inject, cache, pass, or store logger objects.

Outside `config_logging`, `logging.getLogger(...)`, `logging.basicConfig(...)`, `logging.config.*`, logger-purpose constructor or method parameters, instance logger fields, and module-level logger variables are forbidden.

Log records use UTC timestamps and preserve their declared precision. Logging never exposes secrets, credential-bearing URLs, payloads, or raw external data whose contract may contain secrets.
