# 📝 SIDD.md - Team Coordination & Strategy

This document serves as the primary coordination point for **Siddhant (Sidd)** and the Backend/Architecture team. It tracks features, active suggestions, and the ongoing development roadmap.

---

## 🚦 Current Project Status: "Operational Backend"
- **Control Plane**: FastAPI is live with Redis task routing, SQLite analytics, and SSE telemetry.
- **Node Agent**: Hardware-aware daemon with 5s rolling CPU/Memory watchdog and **Reliable Queue (ACK/NACK)** pattern.
- **Sandboxing**: Hardened `--network none` isolation using the **Hybrid Loopback Execution** pattern (executing `urllib`/`fetch` inside containers via `docker exec`).

---

## 🛠️ Feature Roadmap & Team Suggestions

### 1. Hardening & Security (High Priority)
- **Status:** Integrated Team Suggestions from `update.md`.
- [ ] **Docker Task Timeout:** Implement a global 60s timeout for all `exec_run` calls to prevent resource exhaustion from infinite loops. (Suggested by: Siddhant)
- [ ] **Pre-pull Caching:** Update `build_all.sh` to pre-load runtime images into the local Docker engine to ensure "instant" spin-ups. (Suggested by: Siddhant)

### 2. Hardware Expansion
- [ ] **GPU Node Profiling:** Update `registration.py` to detect NVIDIA GPUs (using `nvidia-smi` or similar) and register them under the `q_gpu` hardware type. (Suggested by: Siddhant)
- [ ] **Multi-Language Runtime:** Verify and stress-test the **Node.js runtime** (`runtimes/node-runtime/`) using the hybrid loopback pattern.

### 3. Simulation & "Wow" Factor
- [ ] **Cloud Bursting Simulator:** Develop `mock-cloud/cloud_burst_sim.py` to simulate task overflow to EC2 when local `is_busy` flags are high across the cluster.
- [ ] **GitHub Action Hook:** Create a sample `.github/workflows/deploy.yml` that pings the Control Plane for decentralized deployment.

### 4. Networking (Phase 4)
- [ ] **Tailscale Integration:** Finalize `scripts/setup_tailscale.sh` for stable peer-to-peer connectivity between edge nodes and the control plane.
- [ ] **Cloudflare Tunnel:** Expose the Control Plane API securely without port forwarding.

---

## 📡 Siddhant's Active Directive
*   "Always review all market-down (.md) files to check what changes the team has suggested and implement them."
*   "If review is needed, add it to the implementation plan for confirmation."

---
*Last Updated: 2026-03-30 12:05 PM*
