import time
import redis
import os
import json
import subprocess
import docker
import threading
import yaml
import requests
from watchdog import Watchdog
from registration import register, send_heartbeat, get_node_info

# --- Hardened Sandboxing Configuration (Section 2) ---
SANDBOX_CONFIG = {
    "network_mode": "none",
    "read_only": True,
    "mem_limit": "512m",
    "labels": {"sylk": "true"}
}

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
docker_client = docker.from_env()

watchdog = Watchdog(threshold=config.get("max_cpu_threshold", 80.0))
warm_pool = []
pool_lock = threading.Lock()

def reap_zombies():
    print("Reaping zombie containers...")
    try:
        containers = docker_client.containers.list(all=True, filters={"label": "sylk=true"})
        for c in containers:
            print(f"Removing zombie container: {c.id[:12]}")
            c.remove(force=True)
    except Exception as e:
        print(f"Error reaping zombies: {e}")

def start_warm_container(lang="python"):
    # Map 'default' hardware identifier to 'x86' image tag
    img_arch = "x86" if ARCH == "default" else ARCH
    image = f"sylk-{lang}-runtime:{img_arch}"

    try:
        container = docker_client.containers.run(
            image,
            detach=True,
            **SANDBOX_CONFIG
        )
        # Give the internal server a moment to bind to the port
        time.sleep(1.5)
        with pool_lock:
            warm_pool.append({"container": container, "lang": lang})
        print(f"Warmed up new {lang} container: {container.id[:12]}")
    except Exception as e:
        print(f"Failed to start warm {lang} container: {e}. Check if image {image} exists.")

def maintain_warm_pool():
    # Maintain WARM_POOL_SIZE safely 
    while True:
        with pool_lock:
            current_count = len([c for c in warm_pool if c["lang"] == "python"])
        if current_count >= WARM_POOL_SIZE:
            break
        start_warm_container("python")

QUEUE_NAME = f"q_{ARCH}"

def poll_tasks():
    # Reliable Queue implementation using BRPOPLPUSH
    # Push to a 'processing' queue to ensure task isn't lost if worker dies
    processing_queue = f"{QUEUE_NAME}_processing_{os.getpid()}"
    
    task_data_raw = r.brpoplpush(QUEUE_NAME, processing_queue, timeout=POLLING_INTERVAL)
    
    if task_data_raw:
        task = json.loads(task_data_raw)
        success = execute_task(task)
        
        if success:
            # ACK: Remove from processing queue
            r.lrem(processing_queue, 1, task_data_raw)
            print(f"Task {task.get('task_id')} completed successfully.")
        else:
            # NACK: Push back to main queue
            print(f"Task {task.get('task_id')} failed, requeuing.")
            r.rpush(QUEUE_NAME, task_data_raw)
            r.lrem(processing_queue, 1, task_data_raw)

def heartbeat_loop():
    while True:
        send_heartbeat(CONTROL_PLANE_URL, NODE_ID, watchdog.is_busy())
        time.sleep(30)

def execute_task(task_data):
    language = task_data.get("language", "python")
    task_id = task_data.get("task_id", "unknown")
    code = task_data.get("code", "")

    # Thread-safe extraction: Try to find a pre-warmed container for the language
    container_info = None
    with pool_lock:
        container_info = next((c for c in warm_pool if c["lang"] == language), None)
        if container_info:
            warm_pool.remove(container_info)
    
    if container_info:
        container = container_info["container"]
        # Trigger background refill for the primary language if needed
        if language == "python":
            threading.Thread(target=maintain_warm_pool, daemon=True).start()
    else:
        # Fallback to cold start if no warm container matches language
        print(f"No warm {language} container available. Cold starting...")
        start_warm_container(language)
        with pool_lock:
            if not warm_pool:
                print("Failed to start container for execution.")
                return False
            container_info = warm_pool.pop()
            container = container_info["container"]

    print(f"Executing task {task_id} ({language}) on container {container.id[:12]}")
    
    try:
        import base64
        # Base64 encode the user's code to perfectly bypass all shell escaping nightmares
        b64_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
        
        # Hybrid Loopback Strategy (Aarav's Suggestion):
        # We exec a script INSIDE the network-less container to hit localhost:5000
        if language == "python":
            py_script = f"import urllib.request, json, base64; c = base64.b64decode('{b64_code}').decode('utf-8'); d = json.dumps({{'code': c}}).encode('utf-8'); req = urllib.request.Request('http://localhost:5000/exec', data=d, headers={{'Content-Type': 'application/json'}}); print(urllib.request.urlopen(req).read().decode('utf-8'))"
            exec_command = ["python", "-c", py_script]
        elif language == "node":
            node_script = f"const c = Buffer.from('{b64_code}', 'base64').toString('utf8'); fetch('http://localhost:5000/exec', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{code: c}})}}).then(r=>r.text()).then(console.log);"
            exec_command = ["node", "-e", node_script]
        else:
            print(f"Unsupported language: {language}")
            container.remove(force=True)
            return False

        # Enforce 60s task timeout
        def kill_container():
            try:
                print(f"Timeout reached for task {task_id}. Killing container.")
                container.kill()
            except Exception:
                pass
                
        timeout_timer = threading.Timer(60.0, kill_container)
        timeout_timer.start()

        try:
            exit_code, output = container.exec_run(exec_command)
            result_str = output.decode("utf-8").strip()
            print(f"Task {task_id} result: {result_str}")
        finally:
            timeout_timer.cancel()

        
        # Store result in Redis (Final Acknowledgment)
        r.set(f"result:{task_id}", result_str, ex=3600)
        return True
        
    except Exception as e:
        print(f"Execution failed for {task_id}: {e}")
        return False
    finally:
        # Containers are effectively single-use for total isolation
        container.remove(force=True)

if __name__ == "__main__":
    print(f"Starting Node Agent {NODE_ID} (Arch: {ARCH})")
    if not register(CONTROL_PLANE_URL, NODE_ID):
        print("Warning: Could not register with control plane. Proceeding anyway.")
        
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    reap_zombies()
    maintain_warm_pool()
    
    print(f"Ready. Listening on Redis queue {QUEUE_NAME}...")
    
    while True:
        if not watchdog.is_busy():
            poll_tasks()
        else:
            print(f"System busy (CPU: {watchdog.get_cpu_average():.1f}%), paused polling...")
            time.sleep(5)
        time.sleep(1)
