import redis
import os
import json
import asyncio

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

# Canonical queue names — workers MUST match these exactly
QUEUE_PYTHON = "q_python"
QUEUE_NODE = "q_node"


def queue_task(
    task_id: str,
    code: str,
    language: str = "python",
    callback_url: str = "",
    params: dict = None,
):
    """Route task to the correct language-specific queue."""
    if language == "node":
        queue_name = QUEUE_NODE
    else:
        queue_name = QUEUE_PYTHON

    task_data = {
        "task_id": task_id,
        "code": code,
        "language": language,
        "callback_url": callback_url,
        "params": params or {},
    }
    r.rpush(queue_name, json.dumps(task_data))
    return queue_name


async def fallback_monitor():
    """Moves tasks from q_gpu/q_arm to q_python if they sit too long."""
    while True:
        try:
            for pref in ["gpu", "arm"]:
                queue_name = f"q_{pref}"
                if r.llen(queue_name) > 10:
                    task = r.lpop(queue_name)
                    if task:
                        r.rpush(QUEUE_PYTHON, task)
                        print(
                            f"Fallback: Moved task from {queue_name} to {QUEUE_PYTHON}"
                        )
        except Exception as e:
            print(f"Fallback monitor error: {e}")
        await asyncio.sleep(5)
