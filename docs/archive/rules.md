🛡️ 1. Security & Sandboxing (The "Do No Harm" Rule)

    Container Isolation: Every docker run command or docker-py call must include the following flags: --network none, --read-only, and --memory limits. Never generate code that runs containers with privileged access.

    The /tmp Exception: Only the /tmp directory should be writable (using --tmpfs).

    Credential Safety: Never hardcode API keys, Cloudflare tokens, or Tailscale auth keys. Use os.getenv() or a .env file loader.

    Input Sanitization: Any user-uploaded code snippet must be treated as a malicious payload. Do not allow the Control Plane to execute code directly; it must only pass code to the sandboxed worker nodes.

🐧 2. Multi-Arch Compatibility (The "Pi & Jetson" Rule)

    Architecture Awareness: Always assume the target environment is heterogeneous. Distinguish between amd64 (laptops) and arm64 (Raspberry Pi/Jetson).

    Docker Buildx: Any Docker-related automation must use buildx or specify the --platform flag to prevent image mismatch errors.

    Python Dependencies: Avoid libraries that require complex C-extensions unless they are available as pre-compiled wheels for both x86 and ARM64.

⚙️ 3. Reliability & Fault Tolerance (The "3 AM Stability" Rule)

    The ACK Pattern: When interacting with Redis, use a "Reliable Queue" pattern. Tasks must only be acknowledged (ACK) after the Docker container returns a successful result.

    Graceful Degradation: All network calls (to Redis, Cloudflare, or other nodes) must include a try-except block with a retry limit and a timeout.

    State Management: The Node Agent must be stateless. If it crashes, it should be able to restart, clean up zombie containers, and resume polling without manual intervention.

    Atomic Logging: Every task state change (Queued -> Pulled -> Executing -> Done) must be logged to the SQLite tasks.db immediately to ensure the dashboard reflects reality.

🚀 4. Performance & Functionality (The "Sylk" Feel)

    Async First: The Control Plane (FastAPI) must use async/await for all I/O bound operations (Redis calls, DB writes) to prevent blocking the event loop.

    The Watchdog Protocol: The psutil logic must use a rolling average for CPU load. Avoid "jittery" scaling caused by instantaneous CPU spikes.

    Schema Adherence: All communication between the Frontend, Control Plane, and Node Agent must follow the Pydantic models defined in control-plane/app/schemas.py. No "freestyle" JSON.

    Warm Pool Maintenance: The daemon logic must prioritize keeping the warm pool filled. If a container is used, a replacement should be triggered asynchronously.

📂 Repository Discipline

    Directory Integrity: Do not suggest creating files outside the established folder structure.

    Typing: Use Python type hints (from typing import ...) for all backend and daemon code to improve maintainability and catch bugs early.

    Documentation: Every new function or endpoint must include a brief docstring explaining its role in the mesh.

🚩 Immediate Red Flags (Failure Criteria)

    Generating code that uses shell=True in subprocess calls.

    Suggesting a global redis.flushall() (it will kill everyone's tasks).

    Missing the --platform flag in Docker instructions.

    Hardcoding local IP addresses instead of using service discovery or Tailscale hostnames.