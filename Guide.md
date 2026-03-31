# Project Sylk: Operations & Architecture Guide

Welcome to the internal operations and developer onboarding guide for Project Sylk. This document covers setting up the system environments and provides a deep dive into the mesh architecture.

---

## 🏗️ 1. Architecture Sandbox Overview

Project Sylk leverages a robust pipeline combining FastAPI ingestion, Redis queue distribution, and multi-threaded Agent Daemons executing Docker sandboxes. 

### The Control Plane
- **Location**: `control-plane/`
- **Responsibilities**: Validates generic tasks, injects them into specific Redis queues (`q_default`, `q_arm`, `q_gpu`), and tracks completion statuses via an SQLite telemetry tracker (`tasks.db`). Rate limits request bombing via `slowapi` and configures fallback timeouts to prevent starvation.

### The Runtimes (Warm Pool)
- **Location**: `runtimes/`
- **Responsibilities**: Container definitions for code execution. Employs `docker buildx` for simultaneous `linux/amd64` and `linux/arm64` image builds guaranteeing cross-architecture availability without `Exec format` fatalities.

### The Node Agent
- **Location**: `node-agent/`
- **Responsibilities**: The intelligent device daemon. Implements hardware profiling in real time, background task pulling from Redis using the "Un-ACKed Message" pattern, and executes standard Alpine-based Docker sandboxes on local host.

---

## 💻 2. Local Environment Setup

### Prerequisites
- Python 3.10+
- Docker Engine with `buildx` enabled
- Redis Server (Optionally run via `docker-compose`)

### Booting the Control Plane
The simplest way to start the ingestion Gateway is via Docker Compose.
```bash
cd control-plane
docker-compose up -d --build
```
This spins up both the Redis instance and the Uvicorn-wrapped FastAPI backend. To verify API status, navigate to:
```bash
http://localhost:8000/docs
```

### Initializing a Node Worker
With the control plane active, start a worker node on your machine.
```bash
cd node-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Ensure `config.yaml` points to the accurate Redis IP address of your Control Plane. Boot the daemon:
```bash
python3 worker.py
```
*(The Agent registers its hardware profile and polls its respective queue.)*

---

## 🌍 3. Network Topologies (Advanced)

### Simulating External Stress
Located in `scripts/stress_test.py`, this utility forcefully triggers CPU loads. Use this tool to manually instigate the `watchdog.py` dynamic QoS daemon pauses, simulating host congestion dynamically.

### Tailscale Tunneling Overlay
Operating edge nodes on restricted collegiate or corporate Wi-Fi architectures without static IPs? Deploy Tailscale to weave all devices into a unified zero-trust network.
```bash
cd scripts
chmod +x setup_tailscale.sh
./setup_tailscale.sh
```

### Simulating Cloud Burst
Using `mock-cloud/cloud_burst_sim.py`, you can execute overflow scripts validating how the framework addresses request inundation when local node meshes reach maximal limits.
