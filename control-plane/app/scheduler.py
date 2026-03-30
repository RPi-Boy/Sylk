import redis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def queue_task(task_id: str, code: str, hardware_pref: str):
    queue_name = f"q_{hardware_pref}"
    task_data = {
        "task_id": task_id,
        "code": code
    }
    # TODO: Serialize and push to Redis
    pass
