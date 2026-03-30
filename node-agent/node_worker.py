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

QUEUE_NAME = f"q_{ARCH}"

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
    container = get_container()
    if not container:
        print(f"No container available for {task_id}")
        return False

    threading.Thread(target=fill_pool, daemon=True).start()
    print(f"Executing {task_id} on {container.id[:12]}")

    try:
        b64 = base64.b64encode(code.encode()).decode()
        script = (
            f"const c=Buffer.from('{b64}','base64').toString();"
            f"fetch('http://localhost:5000/exec',{{method:'POST',"
            f"headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify({{code:c}})}}).then(r=>r.text()).then(console.log);"
        )

        timer = threading.Timer(60.0, lambda: container.kill())
        timer.start()
        try:
            _, output = container.exec_run(["node", "-e", script])
            result = output.decode().strip()
            print(f"Result [{task_id}]: {result}")
        finally:
            timer.cancel()

        r.set(f"result:{task_id}", result, ex=3600)
        return True
    except Exception as e:
        print(f"Exec failed [{task_id}]: {e}")
        return False
    finally:
        container.remove(force=True)

def poll_tasks():
    """Use BLPOP instead of deprecated BRPOPLPUSH for Redis 7+ compat."""
    result = r.blpop(QUEUE_NAME, timeout=POLLING_INTERVAL)
    if result:
        _, raw = result
        task = json.loads(raw)
        lang = task.get("language", "python")

        # Only process Node tasks; requeue others
        if lang != "node":
            print(f"Requeuing non-node task {task.get('task_id')}")
            r.rpush(QUEUE_NAME, raw)
            return

        if not execute_task(task):
            print(f"Requeuing failed task {task.get('task_id')}")
            r.rpush(QUEUE_NAME, raw)

def heartbeat_loop():
    while True:
        send_heartbeat(CONTROL_PLANE_URL, NODE_ID, watchdog.is_busy())
        time.sleep(30)

if __name__ == "__main__":
    print(f"=== Sylk Node.js Worker [{NODE_ID}] (Arch: {ARCH}) ===")
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
