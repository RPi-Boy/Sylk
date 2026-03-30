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
        "memory_mb": memory_mb
    }

def register(url, node_id=None):
    info = get_node_info()
    if node_id:
        info["node_id"] = node_id
    try:
        response = requests.post(f"{url}/register", json=info, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Registration failed: {e}")
        return False

def send_heartbeat(url, node_id, is_busy):
    if HAS_PSUTIL:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory_usage = psutil.virtual_memory().percent
    else:
        cpu_usage = 10.0
        memory_usage = 50.0

    payload = {
        "node_id": node_id,
        "cpu_usage": cpu_usage,
        "memory_usage": memory_usage,
        "is_busy": is_busy
    }
    try:
        requests.post(f"{url}/heartbeat", json=payload, timeout=5)
    except Exception as e:
        print(f"Heartbeat failed: {e}")

if __name__ == "__main__":
    print(f"Node Info: {get_node_info()}")
