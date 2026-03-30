import time
import redis
import os
import json
import subprocess
import docker
import threading
import yaml

# --- Hardened Sandboxing Configuration (Section 2) ---
SANDBOX_CONFIG = {
    "network_mode": "none",
    "read_only": True,
    "mem_limit": "512m",
    "labels": {"sylk": "true"}
}

from watchdog import Watchdog
from registration import register, send_heartbeat, get_node_info

config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

NODE_ID = config.get("node_id", "local-node")
CONTROL_PLANE_URL = config.get("control_plane_url", "http://localhost:8000")
POLLING_INTERVAL = config.get("polling_interval", 2)
ARCH = config.get("arch", get_node_info()["hardware_type"])
WARM_POOL_SIZE = 2

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

watchdog = Watchdog(threshold=config.get("max_cpu_threshold", 80.0))
docker_client = docker.from_env()
warm_pool = []

def reap_zombies():
    print("Reaping zombie containers...")
    try:
        containers = docker_client.containers.list(all=True, filters={"label": "sylk=true"})
        for c in containers:
            print(f"Removing zombie container: {c.id[:12]}")
            c.remove(force=True)
    except Exception as e:
        print(f"Error reaping zombies: {e}")

def start_warm_container():
    image = f"sylk-runtime:{ARCH}"
    try:
        container = docker_client.containers.run(
            image,
            detach=True,
            **SANDBOX_CONFIG
        )
        warm_pool.append(container)
        print(f"Warmed up new container: {container.id[:12]}")
    except Exception as e:
        print(f"Failed to start warm container: {e}. Check if image {image} exists.")

def maintain_warm_pool():
    while len(warm_pool) < WARM_POOL_SIZE:
        start_warm_container()

def poll_tasks():
    queue_name = f"q_{ARCH}"
    task = r.blpop(queue_name, timeout=POLLING_INTERVAL)
    if task:
        _, data = task
        execute_task(json.loads(data))

def heartbeat_loop():
    while True:
        send_heartbeat(CONTROL_PLANE_URL, NODE_ID, watchdog.is_busy())
        time.sleep(30)

def execute_task(task_data):
    if not warm_pool:
        start_warm_container()
        if not warm_pool:
            print("No warm containers available.")
            return

    container = warm_pool.pop(0)
    threading.Thread(target=start_warm_container, daemon=True).start()

    code = task_data.get("code", "")
    task_id = task_data.get("task_id", "unknown")
    language = task_data.get("language", "python")
    
    print(f"Executing task {task_id} on container {container.id[:12]}")
    
    try:
        payload_json = json.dumps({"code": code})
        encoded_payload = json.dumps(payload_json) # safely escaped string
        
        if language == "python":
            py_script = f"""
import urllib.request, json
req = urllib.request.Request(
    'http://localhost:5000/exec', 
    data={encoded_payload}.encode('utf-8'),
    headers={{'Content-Type': 'application/json'}}
)
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(str(e))
"""
            exec_command = ["python", "-c", py_script]
        elif language == "node":
            node_script = f"""
fetch('http://localhost:5000/exec', {{
    method: 'POST', 
    headers: {{'Content-Type': 'application/json'}}, 
    body: {encoded_payload}
}}).then(r=>r.text()).then(console.log).catch(console.error);
"""
            exec_command = ["node", "-e", node_script]
        else:
            print(f"Unsupported language: {language}")
            container.remove(force=True)
            return

        exit_code, output = container.exec_run(exec_command)
        result_str = output.decode("utf-8").strip()
        print(f"Task {task_id} result: {result_str}")
        
        # Simple ACK: store result in Redis
        r.set(f"result:{task_id}", result_str, ex=3600)
        
    except Exception as e:
        print(f"Execution failed for {task_id}: {e}")
    finally:
        container.remove(force=True)

if __name__ == "__main__":
    print(f"Starting Node Agent {NODE_ID} (Arch: {ARCH})")
    if not register(CONTROL_PLANE_URL, NODE_ID):
        print("Warning: Could not register with control plane. Proceeding anyway.")
        
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    reap_zombies()
    maintain_warm_pool()
    
    print(f"Ready. Listening on Redis queue q_{ARCH}...")
    while True:
        if not watchdog.is_busy():
            poll_tasks()
        else:
            print(f"System busy (CPU: {watchdog.get_cpu_average():.1f}%), paused polling...")
            time.sleep(5)
