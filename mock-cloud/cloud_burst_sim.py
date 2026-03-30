import redis
import os
import json
import time

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

BURST_THRESHOLD = 5
SIMULATED_COST_PER_TASK = 0.005 # $0.005 per task
total_cost = 0.0

print("☁️  Sylk Cloud Burst Simulator Started...")
print(f"Monitoring q_default for backlog > {BURST_THRESHOLD} tasks.")

while True:
    try:
        backlog = r.llen("q_default")
        if backlog > BURST_THRESHOLD:
            # Burst to cloud
            print(f"⚠️  Backlog high ({backlog} tasks). Bursting to EC2...")
            # Process a small batch to relieve pressure globally
            for _ in range(3):
                task_data_raw = r.lpop("q_default")
                if task_data_raw:
                    task = json.loads(task_data_raw)
                    task_id = task.get("task_id")
                    
                    # Simulate processing compute delay
                    time.sleep(1.5)
                    total_cost += SIMULATED_COST_PER_TASK
                    
                    # Store mock result
                    result_str = "[CLOUD] Execution completed in simulated EC2 environment."
                    r.set(f"result:{task_id}", result_str, ex=3600)
                    print(f"🌩️  Cloud Processed task: {task_id} | Total Burst Cost: ${total_cost:.3f}")
        else:
            time.sleep(2)
    except Exception as e:
        print(f"Simulator error: {e}")
        time.sleep(5)
