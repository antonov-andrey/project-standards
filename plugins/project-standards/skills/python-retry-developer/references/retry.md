# Python Retry Contract

The provider `retry_runtime/DESIGN.md` owns the shared retry-policy and Requests transport interfaces. A project that implements retry behavior MUST use that provider contract unless the user explicitly requires a project-local exception.

One retry boundary encloses the smallest complete atomic operation whose repetition is proven safe. Exactly one runtime layer owns retry for one external operation.

Before enabling retry, the operation owner proves which failures are transient, which side effects may already have happened, whether repetition is idempotent, how partial state is restored or preserved, and which timeout bounds each attempt.

Class-wide automatic retry, reflection-based method wrapping, nested retry layers for the same operation, implicit retry of every exception, and implicit retry of non-idempotent methods are forbidden.

Retry catches only explicitly selected subclasses of `Exception`. `BaseException`, process-control exceptions, generator termination, and async cancellation are never retry policy inputs.

Attempt count always includes the first execution. Names for delays, multipliers, factors, and timeouts state their real unit or mathematical role.

Retries do not log credentials, payloads, URL user information, URL query strings, secret-bearing paths, or raw exception text that may contain external data.
