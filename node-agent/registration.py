import requests
import socket
import platform
import os

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_node_info():
    arch = platform.machine().lower()

    # Mock GPU support based on env variable
    if os.getenv("MOCK_GPU", "false").lower() == "true":
        hardware_type = "gpu"
    elif "arm" in arch or "aarch" in arch:
        hardware_type = "arm"
    else:
        hardware_type = "default"

    if HAS_PSUTIL:
        cpu_cores = psutil.cpu_count() or 1
        memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))
    else:
        cpu_cores = os.cpu_count() or 1
        memory_mb = 4096

    return {
        "node_id": socket.gethostname(),
        "hostname": socket.gethostname(),
        "hardware_type": hardware_type,
        "cpu_cores": cpu_cores,
        "memory_mb": memory_mb,
    }


def register(url, node_id=None, name=None):
    info = get_node_info()
    if node_id:
        info["node_id"] = node_id
    if name:
        info["name"] = name
    try:
        response = requests.post(f"{url}/register", json=info, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Registration failed: {e}")
        return False


def calculate_max_containers(containers_running=0):
    """Calculate max containers this node can run based on available resources.
    Uses 512MB per-container memory limit and CPU estimation.
    Falls back to 10 if psutil is unavailable."""
    try:
        if not HAS_PSUTIL:
            return 10
        mem = psutil.virtual_memory()
        available_mb = mem.available / (1024 * 1024)
        container_mem_mb = 512  # SANDBOX_CONFIG mem_limit

        cpu_count = psutil.cpu_count() or 1
        cpu_pct = psutil.cpu_percent(interval=None)

        if containers_running > 0 and cpu_pct > 5:
            avg_cpu_per = cpu_pct / containers_running
        else:
            avg_cpu_per = 100.0 / cpu_count

        max_from_memory = int(available_mb / container_mem_mb)
        remaining_cpu = max(0, 100 - cpu_pct)
        max_from_cpu = int(remaining_cpu / avg_cpu_per) if avg_cpu_per > 0 else 10

        return max(1, min(max_from_memory, max_from_cpu))
    except Exception:
        return 10


def send_heartbeat(
    url,
    node_id,
    is_busy,
    name=None,
    containers_running=0,
    max_containers=10,
    avg_cold_start_ms=None,
    avg_warm_start_ms=None,
):
    if HAS_PSUTIL:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_usage = psutil.virtual_memory().percent
    else:
        cpu_usage = 10.0
        memory_usage = 50.0

    payload = {
        "node_id": node_id,
        "name": name or node_id,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "is_busy": is_busy,
        "containers_running": containers_running,
        "max_containers": max_containers,
        "avg_cold_start_ms": avg_cold_start_ms,
        "avg_warm_start_ms": avg_warm_start_ms,
    }
    try:
        requests.post(f"{url}/heartbeat", json=payload, timeout=5)
    except Exception as e:
        print(f"Heartbeat failed: {e}")


if __name__ == "__main__":
    print(f"Node Info: {get_node_info()}")
