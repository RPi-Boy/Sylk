import redis
import os
import json
import uuid
import asyncio

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def queue_task(task_id: str, code: str, hardware_pref: str):
    queue_name = f"q_{hardware_pref}"
    task_data = {
        "task_id": task_id,
        "code": code,
        "hardware_pref": hardware_pref
    }
    r.rpush(queue_name, json.dumps(task_data))
    return queue_name

async def fallback_monitor():
    """Moves tasks from q_gpu/q_arm to q_default if they sit too long."""
    while True:
        try:
            for pref in ["gpu", "arm"]:
                queue_name = f"q_{pref}"
                # Move from q_pref to q_default if unhandled. 
                # This is a simplified fallback: in a real system we'd check timestamps.
                # For now, if q_default is empty and others are backed up, we bleed over.
                if r.llen(queue_name) > 10: # arbitrary threshold for simulation
                    task = r.lpop(queue_name)
                    if task:
                        r.rpush("q_default", task)
                        print(f"Fallback: Moved task from {queue_name} to q_default")
        except Exception as e:
            print(f"Fallback monitor error: {e}")
        await asyncio.sleep(5)
