# Docker And Compose Contract

- Build context, Dockerfile, image identity, platform, runtime user, entrypoint, and dependency versions are explicit.
- Configuration and secrets enter through declared runtime boundaries and are not baked into images or committed artifacts.
- Persistent data uses named or explicit host storage; temporary data is marked disposable.
- Health checks test the real service readiness boundary. Startup ordering does not substitute for readiness.
- Networks, ports, capabilities, devices, resource bounds, and service dependencies are no broader than required.
- Destructive cleanup inventories and removes exact containers, images, volumes, and networks. Prefix approximation and unrelated Compose cleanup are forbidden.
- Validate the rendered Compose model and exercise the affected service behavior.
