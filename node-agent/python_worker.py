"""Sylk Python Runtime Worker - Dedicated worker for Python container execution."""
import time, redis, os, json, base64, uuid, docker, threading, yaml, requests
from watchdog import Watchdog
from registration import register, send_heartbeat, get_node_info

SANDBOX_CONFIG = {
    "network_mode": "none",
    "read_only": True,
    "mem_limit": "512m",
    "labels": {"sylk": "true", "sylk-lang": "python"}
}

config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

# Unique node name: config base + short UUID
_base_id = config.get("node_id", "node")
NODE_ID = f"{_base_id}-py-{uuid.uuid4().hex[:6]}"
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
        for c in docker_client.containers.list(all=True, filters={"label": "sylk-lang=python"}):
            print(f"Reaping zombie: {c.id[:12]}")
            c.remove(force=True)
    except Exception as e:
        print(f"Reap error: {e}")

def start_warm_container():
    img_arch = "x86" if ARCH == "default" else ARCH
    image = f"sylk-python-runtime:{img_arch}"
    try:
        container = docker_client.containers.run(image, detach=True, **SANDBOX_CONFIG)
        time.sleep(1.5)
        with pool_lock:
            warm_pool.append(container)
        print(f"Warmed Python container: {container.id[:12]}")
    except Exception as e:
        print(f"Failed to warm Python container: {e}")

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
    # Cold start
    print("Cold starting Python container...")
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

    # Refill pool in background
    threading.Thread(target=fill_pool, daemon=True).start()
    print(f"Executing {task_id} on {container.id[:12]}")

    try:
        b64 = base64.b64encode(code.encode()).decode()
        script = (
            f"import urllib.request, json, base64; "
            f"c=base64.b64decode('{b64}').decode(); "
            f"d=json.dumps({{'code':c}}).encode(); "
            f"req=urllib.request.Request('http://localhost:5000/exec',data=d,"
            f"headers={{'Content-Type':'application/json'}}); "
            f"print(urllib.request.urlopen(req).read().decode())"
        )

        timer = threading.Timer(60.0, lambda: container.kill())
        timer.start()
        try:
            _, output = container.exec_run(["python", "-c", script])
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

        # Only process Python tasks; requeue others
        if lang != "python":
            print(f"Requeuing non-python task {task.get('task_id')}")
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
    print(f"=== Sylk Python Worker [{NODE_ID}] (Arch: {ARCH}) ===")
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
