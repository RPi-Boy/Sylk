import time
import redis
import os
import json
import subprocess
import docker
import requests
from watchdog import Watchdog

# REDIS_URL from env or default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)
client = docker.from_env()

watchdog = Watchdog()

# Default to x86 for testing, in reality read from config.yaml
HW_TYPE = os.getenv("HW_TYPE", "x86")
QUEUE_NAME = f"q_{HW_TYPE}"

def poll_tasks():
    # Reliable Queue implementation using BRPOPLPUSH
    # Push to a 'processing' queue to ensure task isn't lost if worker dies
    processing_queue = f"{QUEUE_NAME}_processing_{os.getpid()}"
    
    task_data_raw = r.brpoplpush(QUEUE_NAME, processing_queue, timeout=5)
    
    if task_data_raw:
        task = json.loads(task_data_raw)
        success = execute_task(task)
        
        if success:
            # ACK: Remove from processing queue
            r.lrem(processing_queue, 1, task_data_raw)
            # Send result back to control plane or output DB via another Redis channel or HTTP
            print(f"Task {task.get('task_id')} completed successfully.")
        else:
            # NACK: Push back to main queue
            print(f"Task {task.get('task_id')} failed, requeuing.")
            r.rpush(QUEUE_NAME, task_data_raw)
            r.lrem(processing_queue, 1, task_data_raw)

def execute_task(task_data):
    task_id = task_data.get('task_id')
    code = task_data.get('code')
    
    print(f"Executing task: {task_id}")
    try:
        # 1. Run container securely
        container = client.containers.run(
            f"sylk-runtime:{HW_TYPE}",
            command=["python", "server.py"], # Assuming python runtime for now
            detach=True,
            network_mode="none",
            read_only=True,
            mem_limit="512m",
            labels={"sylk": "true"}
        )
        
        # 2. Wait for it to spin up (this is slow if not using warm pool, 
        # but the docker team is handling warm pool logic)
        # In a real system we'd exec directly into pre-warmed containers
        
        # For simulation, since network=none, we can't easily curl it.
        # So we write the code to a tmp volume and run it, OR use docker exec.
        # Since server.py is an HTTP server, network_mode='none' actually breaks it
        # UNLESS we use docker exec. Let's adapt to docker exec pattern for strict isolation:
        
        # We will use docker exec to run python directly inside the hardened container
        exec_log = container.exec_run(
            cmd=["python", "-c", code],
            timeout=60 # docker task timeout
        )
        
        print(f"Output: {exec_log.output.decode('utf-8')}")
        
        # 3. Teardown
        container.remove(force=True)
        return True
        
    except Exception as e:
        print(f"Task execution error: {e}")
        return False

if __name__ == "__main__":
    print(f"Worker started. Listening on {QUEUE_NAME}")
    # Cleanup any zombies from previous runs
    try:
        os.system('docker rm -f $(docker ps -a -q --filter "label=sylk") 2>/dev/null')
    except:
        pass
        
    while True:
        if not watchdog.is_busy():
            poll_tasks()
        else:
            print("System busy, sleeping...")
        time.sleep(1)
