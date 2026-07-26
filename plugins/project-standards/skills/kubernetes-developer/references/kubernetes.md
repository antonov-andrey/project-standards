# Kubernetes Contract

## Workload And State Ownership

- Each workload declares its controller, service account, resource requests and limits, probes, termination behavior, restart semantics, and cleanup owner.
- Tracked deployment configuration, runtime `Secret`, persistent service data, and temporary data are distinct owners.
- Local `Kubernetes` stateful services MUST classify each state item as tracked deploy config, runtime `Secret`, persistent service data, or temporary data before adding manifests or tooling; tracked config lives under `deploy/**`, runtime `Secret` must participate in local secret export/restore, persistent service data must live on retained `PersistentVolume` host mounts or external storage, and temporary data may use `emptyDir` only when loss is acceptable.
- Runtime secrets never become tracked manifests or ordinary logs.
- Persistent state uses retained volumes or external storage. `emptyDir` is used only when loss is acceptable.
- Network policy, service discovery, privileged devices, and cloud permissions are explicit and minimal for production semantics.
- A rollout waits on the real readiness boundary and has one observable rollback or recovery path.

## One-Off Job Contract

- One-off operations run through one explicitly named `Job` for the exact operation or migration case.
- The `Job` uses one explicitly selected runnable image and MUST NOT hardcode one local-only image as its only execution path.
- The operation is idempotent or restart-resumable and exposes its real completion, failure, logs, and cleanup boundaries.
- The operation owner waits for successful completion, collects runtime logs, and deletes the `Job` only after success.
- A failed `Job` remains observable and recoverable; cleanup MUST NOT delete the only evidence needed to diagnose or resume the failure.

## Verification

- Render and validate manifests before mutation; verify the affected live behavior after deployment changes.
- When Kubernetes deployment is the required verification surface for changed application assets, deploy the exact current assets before live verification.
- If the normal apply or reconciliation path fails to rebuild or redeploy assets whose inputs changed, fix its change-detection or reconciliation logic instead of using one force-only bypass as the accepted verification path.
