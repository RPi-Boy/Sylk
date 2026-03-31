# Security Policy

## Reporting a Vulnerability

If you discover a potential security vulnerability in Project Sylk, please do not disclose it publicly. Email the maintainers directly. We will review the vulnerability and respond as soon as possible.

## Current Security Gaps (Vulnerabilities & Limitations)

Project Sylk is currently a functional prototype and is actively working toward an enterprise-ready release. As an open-source contributor, you should be aware of the following known security risks in the current design:

### 1. Control Plane Authentication
**Risk Level**: High
**Description**: The Control Plane Gateway endpoints lack sufficient authentication (e.g., Bearer tokens or mTLS). Currently, any user with network access to the Gateway can queue code execution payloads.
**Impact**: Potentially enables denial of service (DoS) and excessive infrastructure cost looping if public endpoints are abused.

### 2. Docker Daemon Sandboxing
**Risk Level**: Medium
**Description**: While tasks are executing in a `--read-only`, `--network none` environment, standard Docker is inherently tied to the host's kernel and runs a daemon as root. Multi-tenant edge computing requires significantly stronger isolation boundaries.
**Mitigation Concept**: Future plans outline a transition from Docker to rootless **Podman** containers or **Firecracker MicroVMs**.

### 3. Internal Mesh Encryption
**Risk Level**: Low (If VPN is properly utilized)
**Description**: The internal communication via Node Agents polling Redis transmits over the wire without SSL/TLS natively. 
**Mitigation Concept**: Setting up Tailscale (mentioned in `scripts/setup_tailscale.sh`) acts as an overlay network encrypting transit, but native application-level TLS termination should be implemented for Redis and the Gateway endpoints.

If you are interested in addressing these security vulnerabilities, please check [CONTRIBUTING.md](CONTRIBUTING.md) for how you can open PRs and get involved!
