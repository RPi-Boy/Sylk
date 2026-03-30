import requests
import socket
import platform
import psutil

def get_node_info():
    return {
        "node_id": socket.gethostname(),
        "hostname": socket.gethostname(),
        "hardware_type": "x86", # Auto-detect logic here
        "cpu_cores": psutil.cpu_count(),
        "memory_mb": int(psutil.virtual_memory().total / (1024 * 1024))
    }

def register(url):
    info = get_node_info()
    try:
        response = requests.post(f"{url}/register", json=info)
        return response.status_code == 200
    except Exception as e:
        print(f"Registration failed: {e}")
        return False

if __name__ == "__main__":
    print(f"Node Info: {get_node_info()}")
