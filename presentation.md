# 🚀 Project Sylk
### The Intelligent Mesh Serverless Blueprint
**"Bring Your Own Compute" (BYOC) Serverless Architecture**

---

## 🌍 The Vision

A decentralized, hardware-aware serverless mesh that dynamically routes computational tasks based on hardware capabilities (CPU, GPU, ARM) and host machine load. It seamlessly turns everyday Laptops, Raspberry Pis, and NVIDIA Jetsons into an interconnected fleet of "Smart Workers."

---

## 🧠 The Control Plane (The Brain)
**A high-concurrency API Gateway and Orchestrator.**

- **Ingestion Strategy:** Powered by FastAPI and multiple Uvicorn workers to maximize single-machine ingestion rates. Protected by `slowapi` HTTP 429 Rate Limiting to prevent crushing the Gateway during spikes.
- **Persistent Telemetry:** Every execution is meticulously logged to a local SQLite database (`tasks.db`), tracking TaskID, Language, Node_ID, Execution Latency, and Status.
- **Fail-safe Fallback Logic:** Tasks sit in specialized Redis queues (e.g., GPU/Jetson). If a specialized node is offline and the 30-second TTL expires, it gracefully re-queues the payload to the "General" x86 pool to guarantee execution.

---

## ⚡ The Execution Engine (The Muscle)
**A near-zero latency "Warm Pool" achieving S3-like simplicity for execution.**

- **Instant Execution:** Maintains a set of idling, pre-warmed Alpine-based Docker containers. When a task arrives, cold-starts are practically eliminated.
- **Hardened Sandboxing:** Malicious code cannot escape.
  - `--network none`: Absolute network isolation.
  - `--read-only`: Immutable root filesystem.
  - `--tmpfs /tmp`: Only a tiny volatile, restricted memory space is writable.
  - `--cpus="1.0" --memory="512m"`: Hard OS-level resource caps.
- **Multi-Arch Support:** `docker buildx` supplies native runtime images for both `linux/amd64` (Laptops) and `linux/arm64` (Pi/Jetson), safely sidestepping Architecture Mismatch errors.

---

## 🤖 The Node Agent (The Data Plane)
**A self-aware daemon turning any device into a contributor.**

- **Hardware Profiling:** On boot, the daemon analyzes its host (architecture, CPU cores, GPU presence) and dynamically registers its telemetry with the Control Plane.
- **Fault Tolerance:** Driven by the "Un-ACKed Message" pattern. If a node crashes mid-execution, the task remains safely unacknowledged in Redis and automatically routes to another node after a timeout.
- **Zombie Cleanup:** Actively sweeps and destroys orphaned Docker containers upon startup to prevent memory leaks and host starvation.

---

## 🎯 The "Killer Feature": Dynamic QoS
**Zero-friction background compute.**

How do we prevent tasks from interrupting a host user's primary workload (like gaming)?
- The node daemon deploys `psutil` as a **Watchdog**.
- It calculates a **5-second rolling average** of host CPU usage in the background (ignoring instantaneous micro-spikes).
- If internal load exceeds 80%, the daemon flips to **"Busy" mode**. It stops polling the Redis queue, drains current executions, and dynamically throttles the mesh load to preserve host performance.

---

## 🌐 Communication & Networking
**Seamless connectivity across firewalls and NATs.**

- **Frontend ↔ Control Plane:** HTTP POST for code ingress. Server-Sent Events (SSE) stream real-time visual progress (Queued → Routed Jetson → Executing → Done) to the UI without messy refreshes.
- **Node ↔ Control Plane:** Fast Redis blocking polling (`blpop`) paired with continuous 30-second heartbeats.
- **External Ingress:** Cloudflare Tunnels expose the Control Plane securely via HTTPS.
- **Internal Mesh VPN:** Tailscale provides a flat VPN layer allowing SSH, debugging, and execution routing across restricted Wi-Fi networks and remote hotspots.
- **Bonus Integration:** A GitHub Actions Webhook endpoint (`POST /webhook/github`) that triggers function deployments directly from a CI/CD pipeline.

---

## 🚧 Overcoming Realities (Hackathon Hurdles)
**How we solved complex engineering landmines.**

- **The ARM/x86 Trap:** A standard x86 container crashes on a Pi. We engineered explicit, separated multi-arch builds (`sylk-runtime:arm`) so the right hardware pulls the right image.
- **The psutil Jitters:** Instant CPU measurements thrash tasks constantly. We smoothed this out with background threading and a `collections.deque` rolling average logic.
- **Zombie Warm Pool Leaks:** Crashing daemons leave containers running alive natively. We enforce a `docker rm -f` reaper on boot and map container lifecycles securely in try/finally blocks.

---

## 🔭 The Production Roadmap (V2)
**Where Sylk goes for Enterprise.**

While this prototype optimizes for speed using Python and Docker, the production tier will evolve:
- **Security:** Transcending standard containers by moving to **Podman** (rootless/daemonless) and **Firecracker MicroVMs** for true, multi-tenant hardware-level isolation.
- **Distribution:** Rewriting the Node Agent natively in **Go** to distribute a single, dependency-free binary file (no python env required).
- **Event Ecosystem:** Expanding event triggers beyond HTTP directly into S3-style bucket hooks and database mutations.
