# Kubernetes Contract

- Each workload declares its controller, service account, resource requests and limits, probes, termination behavior, restart semantics, and cleanup owner.
- Tracked deployment configuration, runtime `Secret`, persistent service data, and temporary data are distinct owners.
- Local `Kubernetes` stateful services MUST classify each state item as tracked deploy config, runtime `Secret`, persistent service data, or temporary data before adding manifests or tooling; tracked config lives under `deploy/**`, runtime `Secret` must participate in local secret export/restore, persistent service data must live on retained `PersistentVolume` host mounts or external storage, and temporary data may use `emptyDir` only when loss is acceptable.
- Runtime secrets never become tracked manifests or ordinary logs.
- Persistent state uses retained volumes or external storage. `emptyDir` is used only when loss is acceptable.
- Jobs are idempotent or restart-resumable and expose completion, failure, logs, and cleanup.
- Network policy, service discovery, privileged devices, and cloud permissions are explicit and minimal for production semantics.
- A rollout waits on the real readiness boundary and has one observable rollback or recovery path.
- Render and validate manifests before mutation; verify the affected live behavior after deployment changes.
