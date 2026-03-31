"""Sylk Python Runtime Worker - Dedicated worker for Python container execution."""
import time, redis, os, json, base64, uuid, docker, threading, yaml, requests, signal, sys, atexit, random, string, socket, math
import concurrent.futures
from watchdog import Watchdog
from registration import register, send_heartbeat, get_node_info, calculate_max_containers

SANDBOX_CONFIG = {
    "network_mode": "none",
    "read_only": True,
    "mem_limit": "512m",
    "labels": {"sylk": "true", "sylk-lang": "python"}
}

config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

_base_id = config.get("node_id", "node")
NODE_ID = f"{_base_id}-py-{uuid.uuid4().hex[:6]}"
CONTROL_PLANE_URL = config.get("control_plane_url", "http://localhost:8000")
POLLING_INTERVAL = config.get("polling_interval", 2)
ARCH = config.get("arch", get_node_info()["hardware_type"])
WARM_POOL_SIZE = 3
TARGET_POOL_SIZE = 3
current_max_cap = 10
IDLE_TIMEOUT = 5  # seconds before draining

REDIS_URL = config.get("redis_url", os.getenv("REDIS_URL", "redis://localhost:6379"))
r = redis.from_url(REDIS_URL)
docker_client = docker.from_env()
watchdog = Watchdog(threshold=config.get("max_cpu_threshold", 80.0))
warm_pool = []
pool_lock = threading.Lock()
shutdown_flag = threading.Event()
active_tasks = 0
active_tasks_lock = threading.Lock()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

# ─── Display Name ────────────────────────────────────────────────────
try:
    _display_user = os.getlogin()
except Exception:
    _display_user = socket.gethostname()
_rand_suffix = ''.join(random.choices(string.ascii_lowercase, k=5))
NODE_NAME = f"{_display_user}-{_rand_suffix}"

# ─── Spinup Time Tracking ────────────────────────────────────────────
cold_start_times = []
warm_start_times = []
timing_lock = threading.Lock()

def _record_timing(t0, is_cold):
    """Record task execution timing for cold/warm start metrics."""
    elapsed_ms = (time.time() - t0) * 1000
    with timing_lock:
        target = cold_start_times if is_cold else warm_start_times
        target.append(elapsed_ms)
        if len(target) > 20:
            target.pop(0)

# ─── Idle Tracking ───────────────────────────────────────────────────
last_task_time = time.time()
task_time_lock = threading.Lock()

def touch_task_time():
    global last_task_time
    with task_time_lock:
        last_task_time = time.time()

def get_idle_seconds():
    with task_time_lock:
        return time.time() - last_task_time

task_arrivals = []
arrival_lock = threading.Lock()

def record_task_arrival():
    now = time.time()
    with arrival_lock:
        task_arrivals.append(now)
        task_arrivals[:] = [t for t in task_arrivals if now - t <= 30]

def get_tps():
    now = time.time()
    with arrival_lock:
        valid = [t for t in task_arrivals if now - t <= 30]
        return len(valid) / 30.0

QUEUE_NAME = "q_python"

# ─── Graceful Shutdown ───────────────────────────────────────────────

def cleanup_containers():
    """Remove all containers in the warm pool."""
    print("\n[SHUTDOWN] Cleaning up warm pool containers...")
    with pool_lock:
        for c in warm_pool:
            try:
                c.remove(force=True)
                print(f"  Removed: {c.id[:12]}")
            except Exception:
                pass
        warm_pool.clear()
    print("[SHUTDOWN] Cleanup complete.")

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) and SIGTERM gracefully."""
    print(f"\n[SHUTDOWN] Received signal {sig}. Shutting down gracefully...")
    shutdown_flag.set()
    cleanup_containers()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
atexit.register(cleanup_containers)

# ─── Container Management ────────────────────────────────────────────

def reap_zombies():
    try:
        for c in docker_client.containers.list(all=True, filters={"label": "sylk-lang=python"}):
            if c.labels.get("sylk-type") == "infrastructure":
                continue
            print(f"Reaping zombie: {c.id[:12]}")
            c.remove(force=True)
    except Exception as e:
        print(f"Reap error: {e}")

def start_warm_container():
    img_arch = "x86" if ARCH == "default" else ARCH
    image = f"sylk-python-runtime:{img_arch}"
    try:
        container = docker_client.containers.run(image, detach=True, **SANDBOX_CONFIG)
        
        # Actively wait for runtime to bind to port 5000
        script = "import socket; socket.create_connection(('127.0.0.1', 5000), timeout=1)"
        ready = False
        for _ in range(20):  # Wait up to ~4 seconds
            time.sleep(0.2)
            exit_code, _ = container.exec_run(["python3", "-c", script])
            if exit_code == 0:
                ready = True
                break
                
        if not ready:
            print(f"Warning: Container {container.id[:12]} took too long to boot Flask server.")

        with pool_lock:
            warm_pool.append(container)
        print(f"Warmed Python container: {container.id[:12]}")
    except Exception as e:
        print(f"Failed to warm Python container: {e}")

def pool_manager_loop():
    """Dynamically maintains warm_pool to match TARGET_POOL_SIZE"""
    while not shutdown_flag.is_set():
        try:
            with pool_lock:
                count = len(warm_pool)
            if count < TARGET_POOL_SIZE:
                start_warm_container()
            elif count > TARGET_POOL_SIZE:
                idle = get_idle_seconds()
                if idle >= IDLE_TIMEOUT:
                    with pool_lock:
                        if len(warm_pool) > TARGET_POOL_SIZE:
                            c = warm_pool.pop()
                            try:
                                c.remove(force=True)
                                print(f"[SCALER] Scaled down container: {c.id[:12]}")
                            except Exception:
                                pass
        except Exception:
            pass
        time.sleep(1)

def get_container():
    """Returns (container, is_cold_start) tuple."""
    with pool_lock:
        if warm_pool:
            return warm_pool.pop(0), False
    print("Cold starting Python container...")
    start_warm_container()
    with pool_lock:
        return (warm_pool.pop(0) if warm_pool else None), True

# ─── Task Execution ──────────────────────────────────────────────────

def execute_task(task):
    touch_task_time()
    t0 = time.time()
    task_id = task.get("task_id", "unknown")
    code = task.get("code", "")
    params = task.get("params", {})
    callback_url = task.get("callback_url", "")
    container, is_cold = get_container()
    if not container:
        print(f"No container available for {task_id}")
        try:
            r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": "No container available"}))
        except Exception:
            pass
        latency_ms = round((time.time() - t0) * 1000, 2)
        post_callback(callback_url, task_id, "No container available", "failed", latency_ms)
        return False

    print(f"Executing {task_id} on {container.id[:12]}")
    try:
        r.publish("sylk_events", json.dumps({"event": "task_executing", "task_id": task_id, "node_id": NODE_ID}))
    except Exception:
        pass

    try:
        params_json = json.dumps(params)
        injected_code = f"import json\nparams = json.loads('{params_json}')\n{code}"

        b64 = base64.b64encode(injected_code.encode()).decode()
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
            exit_code, output = container.exec_run(["python3", "-c", script])
            result = output.decode().strip()
            print(f"Result [{task_id}]: {result}")
        finally:
            timer.cancel()

        if exit_code != 0 or "exec failed" in result or "executable file not found" in result:
            try:
                r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": result[:200]}))
            except Exception:
                pass
            r.set(f"result:{task_id}", result, ex=3600)
            latency_ms = round((time.time() - t0) * 1000, 2)
            post_callback(callback_url, task_id, result, "failed", latency_ms)
            return False

        r.set(f"result:{task_id}", result, ex=3600)
        latency_ms = round((time.time() - t0) * 1000, 2)
        post_callback(callback_url, task_id, result, "done", latency_ms)
        return True
    except Exception as e:
        print(f"Exec failed [{task_id}]: {e}")
        try:
            r.publish("sylk_events", json.dumps({"event": "task_error", "task_id": task_id, "node_id": NODE_ID, "error": str(e)[:200]}))
        except Exception:
            pass
        latency_ms = round((time.time() - t0) * 1000, 2)
        post_callback(callback_url, task_id, str(e), "failed", latency_ms)
        return False
    finally:
        _record_timing(t0, is_cold)
        try:
            container.remove(force=True)
        except Exception:
            pass

# ─── Callback ─────────────────────────────────────────────────────────

def post_callback(callback_url, task_id, result, status, latency_ms=None):
    if not callback_url:
        return
    try:
        full_url = f"{CONTROL_PLANE_URL}{callback_url}"
        payload = {"task_id": task_id, "result": result, "node_id": NODE_ID, "status": status}
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        resp = requests.post(full_url, json=payload, timeout=10)
        print(f"Callback [{task_id}] -> {resp.status_code}")
    except Exception as e:
        print(f"Callback failed [{task_id}]: {e}")

# ─── Polling ──────────────────────────────────────────────────────────

def run_task_wrapper(task):
    global active_tasks
    try:
        execute_task(task)
    finally:
        with active_tasks_lock:
            active_tasks -= 1

def poll_tasks():
    global active_tasks
    
    with active_tasks_lock:
        limit = max(1, current_max_cap - 1)
        current_active = active_tasks
        
    if current_active >= limit:
        time.sleep(0.5)
        return

    if current_active > 0:
        load_ratio = current_active / limit
        time.sleep(load_ratio * 0.5)

    result = r.blpop(QUEUE_NAME, timeout=POLLING_INTERVAL)
    if result:
        _, raw = result
        task = json.loads(raw)
        record_task_arrival()
        try:
            r.publish("sylk_events", json.dumps({"event": "task_picked_up", "task_id": task.get("task_id"), "node_id": NODE_ID}))
        except Exception:
            pass

        with active_tasks_lock:
            active_tasks += 1
            
        executor.submit(run_task_wrapper, task)

def heartbeat_loop():
    while not shutdown_flag.is_set():
        try:
            # Count running containers for THIS worker's language only
            try:
                lang_containers = docker_client.containers.list(
                    filters={"label": "sylk-lang=python"})
                containers_running = len([
                    c for c in lang_containers
                    if c.labels.get("sylk-type") != "infrastructure"
                ])
            except Exception:
                containers_running = 0

            max_cap = calculate_max_containers(containers_running)
            global current_max_cap
            current_max_cap = max_cap

            with timing_lock:
                avg_cold = (sum(cold_start_times) / len(cold_start_times)
                           if cold_start_times else None)
                avg_warm = (sum(warm_start_times) / len(warm_start_times)
                           if warm_start_times else None)

            send_heartbeat(
                CONTROL_PLANE_URL, NODE_ID, watchdog.is_busy(),
                name=NODE_NAME,
                containers_running=containers_running,
                max_containers=max_cap,
                avg_cold_start_ms=round(avg_cold, 1) if avg_cold is not None else None,
                avg_warm_start_ms=round(avg_warm, 1) if avg_warm is not None else None,
            )
        except Exception:
            pass
        time.sleep(10)

def predictive_scaler_loop():
    global TARGET_POOL_SIZE
    while not shutdown_flag.is_set():
        try:
            tps = get_tps()
            with timing_lock:
                avg_time = (sum(warm_start_times) / len(warm_start_times)) if warm_start_times else 500.0
            
            # Predict concurrency needed: tps * avg_exec_time_in_seconds
            base_concurrency = tps * (avg_time / 1000.0)
            
            # User wants 10% scaling sensitivity + 1 buffer
            desired = int(math.ceil(base_concurrency * 1.1)) + 1
            
            # Maintain at least 3 containers unless max_cap is lower
            min_warm = min(3, max(1, current_max_cap))
            
            TARGET_POOL_SIZE = max(min_warm, min(desired, current_max_cap))
        except Exception:
            pass
        time.sleep(2)

# ─── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"=== Sylk Python Worker [{NODE_ID}] ({NODE_NAME}) ===")
    print(f"Queue: {QUEUE_NAME} | Control Plane: {CONTROL_PLANE_URL}")
    if not register(CONTROL_PLANE_URL, NODE_ID, name=NODE_NAME):
        print("Warning: Registration failed. Proceeding anyway.")

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=pool_manager_loop, daemon=True).start()
    threading.Thread(target=predictive_scaler_loop, daemon=True).start()
    reap_zombies()

    print(f"Listening on queue: {QUEUE_NAME}")
    while not shutdown_flag.is_set():
        try:
            if not watchdog.is_busy():
                poll_tasks()
            else:
                print(f"Busy (CPU: {watchdog.get_cpu_average():.1f}%), pausing...")
                time.sleep(5)
            time.sleep(0.5)
        except redis.ConnectionError as e:
            print(f"[ERROR] Redis connection lost: {e}")
            print("  Retrying in 5 seconds...")
            time.sleep(5)
        except redis.TimeoutError as e:
            print(f"[ERROR] Redis timeout: {e}")
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Unexpected error in main loop: {e}")
            time.sleep(3)
