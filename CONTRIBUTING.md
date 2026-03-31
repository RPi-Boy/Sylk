# Contributing to Project Sylk

First off, thank you for considering contributing to Project Sylk! Our goal is to democratize compute power and build a resilient peer-to-peer serverless mesh. 

## Code of Conduct
By participating in this project, you are expected to uphold a welcoming, inclusive, and professional environment. 

## Getting Started

1. **Fork the Repository** and clone it locally.
2. **Branching**: Use a descriptive branch name based on the issue being addressed (`feat/add-podman-support`, `fix/redis-spikes`).
3. **Draft a PR**: Submit a Pull Request targeting the `main` branch. Ensure code meets PEP-8 Python standards (we use `ruff`).
4. **Testing**: Validate your implementation by spinning up a local Control Plane and successfully processing a mock task payload.

---

## Project Lacunas (We need your help!)

While the mesh is operational, several core gaps (lacunas) exist before arriving at the V2 Production Roadmap. These represent high-impact areas where community help is wanted:

### 1. Complete the Frontend Dashboard
**Area**: React / Tailwind (Web)
There is currently no frontend to visually render the "Infinite Scaling" metrics. The frontend needs to subscribe to Server-Sent Events (SSE) from the gateway `tasks.db` to show real-time nodes arriving and dynamically picking up work.

### 2. Podman & Firecracker Migrations
**Area**: DevSecOps / Linux
The current system leverages Docker. For true isolation, we need a configurable toggle inside `Worker` classes allowing operators to select `docker`, `podman`, or `firecracker` as their sandbox execution engine.

### 3. Node Agent Golang Rewrite
**Area**: Go / Distributed Systems
To achieve a "zero-dependency distribution", the Python-based Node Agent daemon needs to be ported entirely to Go. The daemon must retain its `psutil` load-balancing watchdog and cross-compile to arm64 and amd64 seamlessly.

### 4. Event Triggers API
**Area**: Python / FastAPI
Currently, code payloads rely uniquely on HTTP execution. We aim to support mock **S3-bucket hooks** (executing via webhook when a file drops into a virtual volume) and event-bus hooks. 

## Setting up your dev environment
Please refer to the detailed [Guide.md](Guide.md) file which covers installing Docker, Python dependencies, Tailscale overlay networking, and more.
