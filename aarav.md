# Aarav's Implementation Summary - Node Agent (Daemon)

This file documents the features and changes I have successfully implemented for the Daemon component (Execution Engine) of the Sylk mesh. No existing work from other team members was modified in documenting this.

## 1. Watchdog CPU Profiling (`watchdog.py`)
- **Background Threading**: Replaced the blocking `psutil.cpu_percent(interval=1)` calls with a non-blocking background daemon thread. 
- **Rolling Average**: Implemented a 5-second rolling average of the host CPU usage using a fixed-width `collections.deque(maxlen=5)` for highly efficient O(1) history tracking.
- **Jitter Prevention**: The `is_busy()` method now accurately flags the host as "busy" only when the rolling average exceeds the defined threshold (e.g., 80%), completely preventing task polling stalls.

## 2. Node Registration & Heartbeats (`registration.py`)
- **Auto-Architecture Detection**: Wrote a heuristic using `platform.machine().lower()` to automatically tag the node as `arm` (Jetson/RPi) or `x86` (Laptops). This allows the daemon to dynamically listen to the correct architecture queue (e.g., `q_arm` vs `q_x86`).
- **Heartbeat Telemetry**: Implemented the `send_heartbeat()` method. It calculates the live `cpu_usage` and `memory_usage` and fires a status update to the Control Plane every 30 seconds to maintain map/dashboard visibility.

## 3. Worker Orchestration & Sandboxing (`worker.py`)
- **Zombie Cleanup (`reap_zombies`)**: Engineered a startup protocol using `docker-py` that locates and force-removes all orphaned containers left over from previous unexpected shutdowns (using the `sylk=true` label filter).
- **Container Warm Pool**: Created the `maintain_warm_pool()` logic array. When a task is picked up, it pops a running sandbox from the `warm_pool` list, instantly starting an asynchronous refill thread to boot up a replacement.
- **Hybrid Loopback Execution (Network Isolation Fix)**: Strictly enforced the `--network none` security flag. Since standard host port-binding (`-p 5000`) is impossible when networking is fully disabled, I designed an internal `docker exec` workaround.
  - The worker securely encodes the JSON task payload.
  - For Python tasks, it triggers an inline execution script: `python -c "import urllib.request..."` inside the running container.
  - For Node.js tasks, it uses: `node -e "fetch(...)"`.
  - These scripts send a loopback HTTP request to the internal `localhost:5000/exec` wrapper gracefully bypassing the lack of an external network stack.
- **Reliability (`Un-ACKed Message pattern`)**: Completed the `blpop` execution flow. The Daemon parses the output, sets the final execution result directly back into Redis as a final acknowledgment, and reliably tears down the used `read-only` container ensuring a fresh pristine environment for the next task.
