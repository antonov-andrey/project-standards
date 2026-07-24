# Kubernetes Contract

- Each workload declares its controller, service account, resource requests and limits, probes, termination behavior, restart semantics, and cleanup owner.
- Tracked deployment configuration, runtime `Secret`, persistent service data, and temporary data are distinct owners.
- Runtime secrets never become tracked manifests or ordinary logs.
- Persistent state uses retained volumes or external storage. `emptyDir` is used only when loss is acceptable.
- Jobs are idempotent or restart-resumable and expose completion, failure, logs, and cleanup.
- Network policy, service discovery, privileged devices, and cloud permissions are explicit and minimal for production semantics.
- A rollout waits on the real readiness boundary and has one observable rollback or recovery path.
- Render and validate manifests before mutation; verify the affected live behavior after deployment changes.
