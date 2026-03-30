# Sylk: Remaining Tasks & Implementation Roadmap

Based on the directory structure (`node-agent`, `mock-cloud`, `runtimes`, `scripts`, etc.) and the recently completed Control Plane / Frontend integration, here is the comprehensive list of tasks required to bring the Sylk Platform to full operational capacity.

---

## 1. Execution Layer: Node Agent & Secure Runtimes
The worker nodes are currently not actively executing code in sandboxes. This is the most critical next phase.

- [ ] **Finalize `runtimes/` Infrastructure:**
  - [ ] Execute `build_all.sh` to package isolated Docker containers for Python (`python-runtime/`) and Node.js (`node-runtime/`).
  - [ ] Ensure the runtimes properly accept code snippets via HTTP or standard input securely.
- [ ] **Complete `node-agent/worker.py`:**
  - [ ] Integrate the `worker.py` script so that it actively polls the Redis queue (or listens for pushes).
  - [ ] Instead of mocking execution, bind `worker.py` to spawn/call the built runtime Docker containers (passing the actual function code and returning the execution output).
- [ ] **Complete `node-agent/registration.py` & `watchdog.py`:**
  - [ ] Ensure the node registers successfully with the Control Plane upon boot.
  - [ ] Ensure the watchdog properly emits CPU/Memory telemetry and heartbeat data exactly matching the Frontend's updated telemetry specification.

---

## 2. Scalability Layer: Mock Cloud & Bursting
When local edge nodes reach capacity, the system needs to dynamically provision backup resources.

- [ ] **Finalize `mock-cloud/cloud_burst_sim.py`:**
  - [ ] Implement queue depth monitoring. If tasks in the Redis queue exceed a safe threshold or `avg_latency_ms` spikes, automatically spin up a simulated AWS cloud instance to chew through the backlog.
  - [ ] Integrate cost calculation logic to show up in the `metrics.html` dashboard (e.g., standard billing for bursted tasks vs. free edge execution).

---

## 3. Infrastructure & Networking
For physical edge devices to communicate safely with the Control Plane over the internet (without port forwarding).

- [ ] **Tailscale / VPN Integration (`scripts/setup_tailscale.sh`):**
  - [ ] Test the Tailscale setup script to verify a secure mesh network is established between the Control Plane and remote worker nodes (e.g., an actual Raspberry Pi).
  - [ ] Ensure internal routing allows `node-agent` scripts to communicate securely with Redis and the FastAPI `sys` endpoints using Tailscale IP addresses.

---

## 4. Testing, Benchmarking & Polish
Once the entire pipeline is connected, we need to prove it scales and handles failures.

- [ ] **Execute `scripts/stress_test.py`:**
  - [ ] Flood the API with thousands of function requests concurrently.
  - [ ] Validate that the Control Plane API does not crash (Rate Limiters hold up).
  - [ ] Validate that the fallback monitor / fallback queue functions properly when hardware requirements aren't implicitly met.
- [ ] **Frontend Final Polish:**
  - [ ] If required, ensure the `projects.html` dashboard natively aligns with a user's persistent GitHub repositories (if CD integration is planned).
  - [ ] Ensure the UI gracefully handles scenarios where *all* nodes are disconnected.

---
*Roadmap generated automatically after verifying the Frontend ↔ Backend integration. The immediate focus should now shift to the **Execution Layer (Node Agent)**.*
