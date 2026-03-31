# Session Learnings

### Repository Structure & Tooling
* **Python Tooling (`ruff`)**: Utilizing `ruff` for formatting and linting ensures PEP-8 compliance is extremely fast and robust for edge-device frameworks.
* **API Unused Variable Catches**: We identified several unused variables in the `control-plane` routes (`queue_name` and `token` variables), which were successfully cleaned up via direct ast-based checks, improving runtime purity and removing `F841` warnings.

### Architectural V2 Needs
* Highlighted the explicit need to transition the execution engine from Docker to true MicroVMs (`podman` rootless / `firecracker`). Given Docker's default root-bound daemon, multi-tenant execution needs harder sandboxing to prevent kernel-level escalations.
