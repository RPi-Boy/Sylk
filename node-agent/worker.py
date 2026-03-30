import time
import redis
import os
import json
import subprocess
from watchdog import Watchdog

# REDIS_URL from env or default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

watchdog = Watchdog()

def poll_tasks():
    # TODO: Poll specific architecture queue
    # q_default, q_arm, or q_gpu
    task = r.blpop("q_default", timeout=30)
    if task:
        _, data = task
        execute_task(json.loads(data))

def execute_task(task_data):
    # TODO: Docker-py implementation
    print(f"Executing task: {task_data}")

if __name__ == "__main__":
    while True:
        if not watchdog.is_busy():
            poll_tasks()
        else:
            print("System busy, sleeping...")
        time.sleep(5)
