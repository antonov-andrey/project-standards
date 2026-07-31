# Docker And Compose Contract

- Build context, Dockerfile, image identity, platform, runtime user, entrypoint, and dependency versions are explicit.
- One build or release graph defines exactly one canonical image identity for each runtime or tool family, including build bases and directly deployed third-party images, and every compatible consumer reuses it. Selector keys and image build arguments use the runtime or tool family name; consumer-specific aliases and variants that differ only by distribution, mirror, or flavor are forbidden.
- An additional image variant is allowed only for a proven ABI, libc, vendor final-image, or security-boundary incompatibility. Its name describes that compatibility boundary, the project design records the reason, and an executable build or compatibility test protects the exception.
- Every image change inventories the complete affected build and release graph by upstream repository family. A project with centralized selectors tests the exact allowed duplicate-family exception set, and direct deployment manifests test identity equality across compatible consumers; cross-project heuristics do not replace this semantic compatibility review.
- Configuration and secrets enter through declared runtime boundaries and are not baked into images or committed artifacts.
- Persistent data uses named or explicit host storage; temporary data is marked disposable.
- Health checks test the real service readiness boundary. Startup ordering does not substitute for readiness.
- Networks, ports, capabilities, devices, resource bounds, and service dependencies are no broader than required.
- Destructive cleanup inventories and removes exact containers, images, volumes, and networks. Prefix approximation and unrelated Compose cleanup are forbidden.
- Validate the rendered Compose model and exercise the affected service behavior.
