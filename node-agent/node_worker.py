"""Sylk Node.js Runtime Worker - Dedicated worker for Node container execution."""
import time, redis, os, json, base64, uuid, docker, threading, yaml, requests
from watchdog import Watchdog
from registration import register, send_heartbeat, get_node_info

SANDBOX_CONFIG = {
    "network_mode": "none",
    "read_only": True,
    "mem_limit": "512m",
    "labels": {"sylk": "true", "sylk-lang": "node"}
}

config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

_base_id = config.get("node_id", "node")
NODE_ID = f"{_base_id}-js-{uuid.uuid4().hex[:6]}"
CONTROL_PLANE_URL = config.get("control_plane_url", "http://localhost:8000")
POLLING_INTERVAL = config.get("polling_interval", 2)
ARCH = config.get("arch", get_node_info()["hardware_type"])
WARM_POOL_SIZE = 2

REDIS_URL = config.get("redis_url", os.getenv("REDIS_URL", "redis://localhost:6379"))
r = redis.from_url(REDIS_URL)
docker_client = docker.from_env()
watchdog = Watchdog(threshold=config.get("max_cpu_threshold", 80.0))
warm_pool = []
pool_lock = threading.Lock()

# --- HARDCODED QUEUE NAME: language-specific ---
QUEUE_NAME = "q_node"

def reap_zombies():
    try:
        for c in docker_client.containers.list(all=True, filters={"label": "sylk-lang=node"}):
            print(f"Reaping zombie: {c.id[:12]}")
            c.remove(force=True)
    except Exception as e:
        print(f"Reap error: {e}")

def start_warm_container():
    img_arch = "x86" if ARCH == "default" else ARCH
    image = f"sylk-node-runtime:{img_arch}"
    try:
        container = docker_client.containers.run(image, detach=True, **SANDBOX_CONFIG)
        time.sleep(1.5)
        with pool_lock:
            warm_pool.append(container)
        print(f"Warmed Node.js container: {container.id[:12]}")
    except Exception as e:
        print(f"Failed to warm Node.js container: {e}")

def fill_pool():
    while True:
        with pool_lock:
            count = len(warm_pool)
        if count >= WARM_POOL_SIZE:
            break
        start_warm_container()

def get_container():
    with pool_lock:
        if warm_pool:
            return warm_pool.pop(0)
    print("Cold starting Node.js container...")
    start_warm_container()
    with pool_lock:
        return warm_pool.pop(0) if warm_pool else None

def execute_task(task):
    task_id = task.get("task_id", "unknown")
    code = task.get("code", "")
    params = task.get("params", {})
    callback_url = task.get("callback_url", "")
    container = get_container()
    if not container:
        print(f"No container available for {task_id}")
        r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": "No container available"}))
        post_callback(callback_url, task_id, "No container available", "failed")
        return False

    threading.Thread(target=fill_pool, daemon=True).start()
    print(f"Executing {task_id} on {container.id[:12]}")
    r.publish("sylk_events", json.dumps({"event": "task_executing", "task_id": task_id, "node_id": NODE_ID}))

    try:
        # Inject params into code as a global variable
        params_json = json.dumps(params)
        injected_code = f"const params = {params_json};\n{code}"

        b64 = base64.b64encode(injected_code.encode()).decode()
        script = (
            f"const c=Buffer.from('{b64}','base64').toString();"
            f"fetch('http://localhost:5000/exec',{{method:'POST',"
            f"headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify({{code:c}})}}).then(r=>r.text()).then(console.log);"
        )

        timer = threading.Timer(60.0, lambda: container.kill())
        timer.start()
        try:
            exit_code, output = container.exec_run(["node", "-e", script])
            result = output.decode().strip()
            print(f"Result [{task_id}]: {result}")
        finally:
            timer.cancel()

        # Detect OCI / exec errors
        if "exec failed" in result or "executable file not found" in result:
            r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": result[:200]}))
            r.set(f"result:{task_id}", result, ex=3600)
            post_callback(callback_url, task_id, result, "failed")
            return False

        r.set(f"result:{task_id}", result, ex=3600)
        post_callback(callback_url, task_id, result, "done")
        return True
    except Exception as e:
        print(f"Exec failed [{task_id}]: {e}")
        r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": str(e)[:200]}))
        post_callback(callback_url, task_id, str(e), "failed")
        return False
    finally:
        container.remove(force=True)


def post_callback(callback_url, task_id, result, status):
    """POST the result back to the control plane callback endpoint."""
    if not callback_url:
        return
    try:
        full_url = f"{CONTROL_PLANE_URL}{callback_url}"
        payload = {
            "task_id": task_id,
            "result": result,
            "node_id": NODE_ID,
            "status": status
        }
        resp = requests.post(full_url, json=payload, timeout=10)
        print(f"Callback [{task_id}] -> {resp.status_code}")
    except Exception as e:
        print(f"Callback failed [{task_id}]: {e}")


def poll_tasks():
    """BLPOP from q_node — only Node.js tasks arrive here."""
    result = r.blpop(QUEUE_NAME, timeout=POLLING_INTERVAL)
    if result:
        _, raw = result
        task = json.loads(raw)

        event_picked_up = {"event": "task_picked_up", "task_id": task.get("task_id"), "node_id": NODE_ID}
        r.publish("sylk_events", json.dumps(event_picked_up))

        success = execute_task(task)
        if success:
            event_completed = {"event": "task_completed", "task_id": task.get("task_id"), "node_id": NODE_ID}
            r.publish("sylk_events", json.dumps(event_completed))
        else:
            event_failed = {"event": "task_failed", "task_id": task.get("task_id"), "node_id": NODE_ID}
            r.publish("sylk_events", json.dumps(event_failed))

def heartbeat_loop():
    while True:
        send_heartbeat(CONTROL_PLANE_URL, NODE_ID, watchdog.is_busy())
        time.sleep(30)

if __name__ == "__main__":
    print(f"=== Sylk Node.js Worker [{NODE_ID}] ===")
    print(f"Queue: {QUEUE_NAME} | Control Plane: {CONTROL_PLANE_URL}")
    if not register(CONTROL_PLANE_URL, NODE_ID):
        print("Warning: Registration failed. Proceeding anyway.")

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    reap_zombies()
    fill_pool()

    print(f"Listening on queue: {QUEUE_NAME}")
    while True:
        if not watchdog.is_busy():
            poll_tasks()
        else:
            print(f"Busy (CPU: {watchdog.get_cpu_average():.1f}%), pausing...")
            time.sleep(5)
        time.sleep(0.5)
