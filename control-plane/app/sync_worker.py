import time
import os
import redis
from sqlalchemy.orm import Session
from app.database import SessionLocal, TaskRecord, TaskStatusEnum

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.from_url(REDIS_URL)

def sync_results():
    db: Session = SessionLocal()
    try:
        # Scan Redis for any resulting ACKed tasks from Node Agents
        for key in r.scan_iter("result:*"):
            task_id = key.decode("utf-8").split(":")[1]
            result_val = r.get(key)
            if result_val:
                result_str = result_val.decode("utf-8")
                
                # Update SQLite Analytics database
                task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
                if task_record and task_record.status != TaskStatusEnum.DONE:
                    task_record.status = TaskStatusEnum.DONE
                    task_record.result = result_str
                    db.commit()
                    print(f"Synced result for task {task_id} to database.")
                
                # Delete the key from Redis after successful sync to prevent duplicate work
                r.delete(key)
    except Exception as e:
        print(f"Sync error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Starting Control Plane Sync Worker pointing to {REDIS_URL}...")
    while True:
        sync_results()
        time.sleep(2)  # Non-blocking polling interval
