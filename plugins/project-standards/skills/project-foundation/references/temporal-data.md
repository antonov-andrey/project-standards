# Temporal Data Contract

- Every datetime that represents an instant uses UTC as its canonical internal timezone.
- Runtime instant values must be timezone-aware and normalized to UTC. Removing `tzinfo` from an instant is forbidden.
- At an ingress boundary:
  - an offset-aware value is converted to UTC;
  - an offset-less value may be accepted only when the external contract explicitly declares it to be UTC, after which UTC timezone information is attached;
  - otherwise the boundary must reject the value or convert it from an explicitly declared source timezone.
- Persistence, internal messages, caches, and background jobs preserve the exact UTC instant and required precision.
- A storage protocol that cannot represent timezone-aware values may use naive UTC only inside its adapter boundary. The adapter must enforce UTC and restore timezone-aware UTC immediately after reading.
- APIs serialize instants as RFC 3339 UTC values with `Z` or `+00:00`.
- Conversion to a user or account timezone happens only at the presentation boundary, such as the frontend or a human-oriented export. A presentation value must not replace the canonical UTC value.
- A calendar date, local time of day, or timezone-dependent business schedule is not an instant and must be modeled separately. When such a value depends on a timezone, it stores an explicit IANA timezone identifier.
