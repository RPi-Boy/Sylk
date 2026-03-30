import requests
import socket
import platform
import psutil

def get_node_info():
    arch = platform.machine().lower()
    
    # Simple heuristic to distinguish GPU/ARM/X86
    if "arm" in arch or "aarch" in arch:
        hardware_type = "arm"
    else:
        hardware_type = "x86"

    return {
        "node_id": socket.gethostname(),
        "hostname": socket.gethostname(),
        "hardware_type": hardware_type,
        "cpu_cores": psutil.cpu_count() or 1,
        "memory_mb": int(psutil.virtual_memory().total / (1024 * 1024))
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
    payload = {
        "node_id": node_id,
        "cpu_usage": psutil.cpu_percent(interval=None),
        "memory_usage": psutil.virtual_memory().percent,
        "is_busy": is_busy
    }
    try:
        requests.post(f"{url}/heartbeat", json=payload, timeout=5)
    except Exception as e:
        print(f"Heartbeat failed: {e}")

if __name__ == "__main__":
    print(f"Node Info: {get_node_info()}")
