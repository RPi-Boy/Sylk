<div align="center">
  <h1>Project Sylk</h1>
  <p><b>The Intelligent Mesh Serverless Blueprint</b></p>
  <p><i>A decentralized, hardware-aware serverless mesh that dynamically routes computational tasks based on cost and capability.</i></p>
</div>

---

## Overview

Project Sylk introduces a **"Bring Your Own Compute" (BYOC)** serverless architecture. It seamlessly turns everyday devices like Laptops, Raspberry Pis, and NVIDIA Jetsons into an interconnected fleet of "Smart Workers." 

Instead of relying solely on expensive centralized cloud providers, Sylk routes tasks dynamically based on hardware capabilities (CPU, GPU, ARM) and the host machine's current load—achieving a near-zero latency execution environment.

## Key Features

- **Dynamic Quality of Service (QoS)**: The node daemon deploys a watchdog calculating a 5-second rolling average of host CPU usage. If it exceeds 80%, the node pauses task ingestion to preserve the host's primary workload performance.
- **Hardware-Aware Task Routing**: Automatically detects your hardware architecture and routes jobs appropriately. 
- **Lightning-Fast Execution**: Maintains a "Warm Pool" of idling pre-warmed Alpine-based Docker containers.
- **Multi-Arch Support**: Multi-architecture runtime support ensures the right Docker container goes to the right device.
- **Hardened Sandboxing**: `--network none`, `--read-only`, and strict resource caps prevent exfiltration, persistent malware, and RAM exhaustion.

## Architecture

1. **The Control Plane**: A high-concurrency API Gateway powered by FastAPI, backed by Redis and protected by slowapi rate-limiting.
2. **The Execution Engine**: A Docker-powered runtime execution engine that isolates task payloads.
3. **The Node Agent**: A self-aware Python daemon that analyzes host hardware, polls Redis for unacknowledged messages, and executes tasks.

## Quickstart

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/Sylk.git
   cd Sylk
   ```

2. Start the **Control Plane**:
   ```bash
   cd control-plane
   docker-compose up -d
   ```

3. Start a **Node Agent**:
   ```bash
   cd node-agent
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 worker.py
   ```

## Documentation

- [Contributor Guide](Guide.md) - Deep dive into architecture, APIs, and setting up the full mesh.
- [Security Policy](SECURITY.md) - Details on sandboxing protections and known architectural vulnerabilities.
- [Contributing](CONTRIBUTING.md) - Open lacunas and guidelines to contribute to Project Sylk.
