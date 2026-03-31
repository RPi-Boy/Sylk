# Project Sylk: Operational Plan

Vision: A decentralized, hardware-aware, "Bring Your Own Compute" (BYOC) serverless mesh that intelligently routes tasks between local edge devices (Jetson, RPi) and cloud providers based on cost and capability.
## Phase 1: The Control Plane (The Brain)

Primary Lead: Sidd + Frontend Dev
Goal: Establish the ingestion layer and the task routing logic.
### 1.1 API & Ingestion Setup

    Implement FastAPI with Uvicorn using multiple workers (--workers 4+) to handle concurrent ingestion.

    Integrate SlowAPI for 429 Rate Limiting to protect the Control Plane from request bombardment.

    *Hurdle: The SPOF Bottleneck. Even with multi-workers, a single machine is a bottleneck.

        Mitigation: Keep the logic inside the API extremely "thin"—simply validate the JSON and dump it into Redis immediately.

### 1.2 Redis Task Queuing

    Initialize Redis with three distinct queues: q_default (x86), q_arm (Pi), and q_gpu (Jetson/AI).

    *Hurdle: Task Starvation. A GPU task might sit forever if the Jetson is offline.

        Mitigation: Implement a "Fallback Timer." If a task stays in q_gpu for > 30s, re-route it to q_default for standard CPU execution.

### 1.3 Persistent Logging (Analytics)

    Setup a local SQLite database (sylk_analytics.db) to track every execution.

    Fields: task_id, node_id, hardware_type, latency_ms, simulated_cost, status.

## Phase 2: The Execution Engine (The Muscle)

Primary Lead: Docker Specialist
Goal: Create a secure, lightning-fast "Warm Pool" environment.
### 2.1 Multi-Arch Image Building

    Use docker buildx to create images for both linux/amd64 and linux/arm64.

    Base image: python:3.11-alpine running a minimal HTTP wrapper on port 5000.

### 2.2 Hardened Sandboxing

    Finalize the docker run command flags:

        --network none: Prevent data exfiltration.

        --read-only: Prevent persistent malware.

        --memory 512m: Prevent RAM exhaustion.

    *Hurdle: Architecture Mismatch. Pulling the wrong image on a Pi will cause an Exec format error.

        Mitigation: Tag images explicitly as sylk-runtime:arm and sylk-runtime:x86.

### 2.3 Warm Pool Management

    Create a manager script that maintains N idling containers.

    *Hurdle: Zombie Containers. Crashed daemons leave orphans.

        Mitigation: Use a "reaper" function in the daemon that runs docker rm -f $(docker ps -a -q --filter "label=sylk") on startup.

## Phase 3: The Node Agent (The Intelligence)

Primary Lead: Sidd + Daemon Specialist
Goal: Turn hardware into smart "Spot Instances."
### 3.1 Hardware Profiling & Registration

    On startup, the daemon must auto-detect architecture and GPU availability.

    Send a POST /register to the Control Plane to appear on the dashboard.

### 3.2 The Watchdog Loop (psutil)

    Implement a background thread to calculate a 5-second rolling average of host CPU usage.

    *Hurdle: The Jitter Factor. Raw CPU spikes (like opening a browser tab) could trigger unnecessary task evictions.

        Mitigation: Only flip the is_busy flag if the 5-second average exceeds 80%.

### 3.3 Task Execution & Acknowledgement

    Implement the "Un-ACKed Message" pattern.

    If execution fails, the daemon does not send the ACK to Redis, ensuring the task is re-queued for another node.

## Phase 4: Networking & Ingress

Primary Lead: Sidd
Goal: Connect the mesh across different networks.
### 4.1 External Ingress

    Deploy Cloudflare Tunnels to expose the Control Plane.

    *Hurdle: Tunnel Timeouts. Cloudflare may drop long-lived WebSocket connections.

        Mitigation: Implement a recursive "heartbeat" and auto-reconnect logic in the Node Agent.

### 4.2 Internal Mesh

    Install Tailscale on the headless Jetson/RPi.

    Ensure the Node Agent points to the Control Plane’s Tailscale IP for stable internal polling.

## Phase 5: Frontend & "Wow" Factor

Goal: Visual proof of the "Infinite Scaling" claim.
###5.1 Real-Time Telemetry

    Create a dashboard showing cards for every registered node.

    Use Server-Sent Events (SSE) to stream task status from the API to the UI.

### 5.2 The "Cloud Bursting" Demo

    Integrate a simulated EC2 Tier.

    When the local mesh is "Busy," show the dashboard routing tasks to the cloud and the "Simulated Cost" counter starting to tick.

### 5.3 GitHub Action Integration

    Write a sample .github/workflows/deploy.yml that pings the Sylk Webhook.

    *Hurdle: Webhook Security. Anyone with the URL could spam your cluster.

        Mitigation: (Optional for Hackathon) Use a simple X-Sylk-Token header for basic authentication.

### V2 Production Roadmap (For the Pitch)

    Security: Transition from Docker to Podman (rootless) and Firecracker (MicroVM isolation).

    Language: Rewrite Node Agent in Go for zero-dependency distribution.

    Ecosystem: Expand triggers beyond HTTP to include S3-style bucket events and database hooks.


### Friday Night "Happy Path" Checklist

    [ ] FastAPI can receive a code string.

    [ ] Redis stores and returns that string.

    [ ] A remote laptop pulls that string and runs it in a Docker container.

    [ ] The result is returned to the original requester.


## Repository Structure

Sylk/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Action for the Webhook Brownie Point
├── control-plane/              # THE BRAIN (FastAPI + Redis)
│   ├── app/
│   │   ├── main.py             # FastAPI entry point (Uvicorn workers)
│   │   ├── routes.py           # API Endpoints (Execution, Registration, SSE)
│   │   ├── scheduler.py        # Logic for routing to specific Redis queues
│   │   ├── database.py         # SQLite / SQLAlchemy setup for analytics
│   │   └── schemas.py          # Pydantic models for shared JSON structures
│   ├── tasks.db                # Persistent SQLite log (Deliverable 3)
│   ├── requirements.txt
│   └── docker-compose.yml      # To spin up FastAPI + Redis locally
├── node-agent/                 # THE MUSCLE (Python Daemon)
│   ├── watchdog.py             # psutil logic (The "Killer Feature")
│   ├── worker.py               # Redis polling + Docker-py orchestration
│   ├── registration.py         # Heartbeat and hardware profiling logic
│   ├── config.yaml             # Local node settings (ID, max CPU threshold)
│   └── requirements.txt
├── runtimes/                   # THE SANDBOX (Docker environments)
│   ├── python-runtime/
│   │   ├── Dockerfile          # Multi-arch (buildx) Alpine image
│   │   └── server.py           # Lightweight HTTP wrapper for exec()
│   ├── node-runtime/
│   │   ├── Dockerfile
│   │   └── server.js
│   └── build_all.sh            # Script to rebuild all runtime images
├── frontend/                   # THE FACE (React/Tailwind)
│   ├── public/
│   ├── src/
│   │   ├── components/         # NodeCards, Terminal, AnalyticsCharts
│   │   ├── App.js              # Main Dashboard logic
│   │   └── api.js              # Fetch/SSE connection logic
│   ├── package.json
│   └── tailwind.config.js
├── mock-cloud/                 # THE SIMULATION (EC2 Tier)
│   └── cloud_burst_sim.py      # Script to simulate paid cloud instances
├── scripts/                    # UTILITIES
│   ├── stress_test.py          # Script to hammer the CPU for the demo
│   └── setup_tailscale.sh      # Automation for connecting RPi/Jetson
├── docs/
│   ├── architecture_diagrams/  # Your Sylk-2.drawio.png files
│   └── api_spec.md             # Shared JSON definitions
├── plan.md                     # Our master strategy
└── README.md                   # The Pitch + Setup Instructions