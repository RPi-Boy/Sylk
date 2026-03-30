# Docker Team - Working Task List & Specifications

This document outlines the specific tasks and technical specifications for the Docker/Execution Engine part of the Sylk project. It serves as our coordination point.

## 1. Multi-Architecture Image Building
**Goal:** Create lightweight, executable sandbox images that work seamlessly on both x86 machines and ARM-based edge devices (Raspberry Pi, Jetson).

*   [x] **Setup `buildx`:** Configure `docker buildx` for multi-architecture builds.
*   [x] **Python Runtime (`runtimes/python-runtime/Dockerfile`):**
    *   **Base Image:** `python:3.11-alpine`
    *   **Specs:** Include a minimal HTTP wrapper running on port 5000 to receive and execute the task code.
*   [x] **Node.js Runtime (`runtimes/node-runtime/Dockerfile`):**
    *   **Base Image:** Appropriate lightweight Node.js Alpine image.
*   [x] **Explicit Tagging:** Tag images specifically to avoid `Exec format error` during pulls:
    *   `sylk-runtime:x86` (for linux/amd64)
    *   `sylk-runtime:arm` (for linux/arm64)
*   [x] **Automation (`runtimes/build_all.sh`):** Write a bash script to rebuild and tag all runtime images cleanly.

## 2. Hardened Sandboxing Configuration
**Goal:** Ensure that user-provided code runs in a strictly isolated environment without network or filesystem access.

*   [ ] **Define `docker run` execution flags:**
    *   `--network none`: Completely disable networking to prevent data exfiltration.
    *   `--read-only`: Mount the container's root filesystem as read-only to prevent persistent malware.
    *   `--memory 512m`: Implement a hard memory limit to prevent RAM exhaustion and Host OS crashes.
    *   Add identifying labels (e.g., `--label sylk`) for easier container management.

## 3. Warm Pool & Lifecycle Management
**Goal:** Maintain instantaneous execution times by managing a pool of pre-warmed idle containers and handling cleanup dynamically.

*   [ ] **Warm Pool Manager:** Develop the logic to spin up and maintain $N$ idling sandbox containers.
*   [ ] **Zombie Reaper:** Implement a startup cleanup function to catch crashed daemon orphans.
    *   **Command Spec:** `docker rm -f $(docker ps -a -q --filter "label=sylk")`
*   [ ] **Node Agent Orchestration (`node-agent/worker.py`):** Use `docker-py` to implement the container lifecycle API (pull, start pre-warmed, exec code, return result, teardown/recycle).

## 4. Control Plane Infrastructure
**Goal:** Containerize the Control Plane dependencies for easy local testing.

*   [ ] **Control Plane Compose (`control-plane/docker-compose.yml`):**
    *   Define a service for the FastAPI application (matching `app/main.py`).
    *   Define a service for the Redis instance (the task queue).
    *   Ensure appropriate volume mapping for the `sylk_analytics.db` persistent SQLite log.

---
*Note: Any updates to the required container specs or security flags must be logged in this document before implementation.*

## 5. Docker Build & Performance Tests
**Goal:** Verify layer caching optimization and measure container warmup and scaling speeds for the execution engine.

*   [x] **Dockerfile Caching:** Reordered instructions (`RUN pip install --no-cache-dir flask` before `COPY server.py .`) to prevent unnecessary layer invalidation.
    *   **Initial Build Time:** ~18.50s (installing dependencies)
    *   **Cached Build Time:** ~0.85s (caching confirmed working)
*   [x] **Hardened Security:**
    *   Added non-root user (`sylkuser`) to prevent container breakout.
    *   Used `--no-cache-dir` in pip to reduce attack surface and image size.
*   [x] **Container Lifecycle (Warmup):**
    *   Container 1 (Warm): 0.412s
    *   Container 2 (Warm): 0.395s
*   [x] **Container Scaling (Scale to 5):**
    *   Container 3: 0.401s
    *   Container 4: 0.388s
    *   Container 5: 0.415s
    *   **Average Spin-Up Latency:** 0.402s

## 6. Ideas for Spin-up Optimization (Future)
**Proposed strategies to push below the ~400ms threshold:**

1.  **Switch to FastAPI/Uvicorn**: While Flask is simple, Uvicorn (ASGI) can be even faster at initialization and handling concurrent requests.
2.  **App Pre-loading**: Use a production server like Gunicorn with `--preload` to load the Python environment once in memory (improves response time).
3.  **Distroless Images**: Moving from Alpine to Google's Distroless images can further reduce image size and improve security (no shell/no package manager).
4.  **CRIU (Checkpoint/Restore in Userspace)**: Advanced technique to "freeze" a running container once initialized and "thaw" it instantly for new tasks. This could bring spinup times into the low tens of milliseconds.
5.  **Multi-stage Builds**: Ensure that compilers and build tools (if needed for dependencies) are not present in the final runtime image.
6.  **Local Image Registry**: Running a local `zot` or `registry:2` on the edge nodes to avoid any network latency during image pulls.
