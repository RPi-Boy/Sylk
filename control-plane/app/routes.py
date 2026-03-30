import uuid
import os
import json
import time
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from sse_starlette.sse import EventSourceResponse

from . import schemas
from .database import SessionLocal, TaskRecord, TaskStatusEnum
from .scheduler import queue_task, r
from . import auth

router = APIRouter()

# --- Dependencies ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_node_token(x_sylk_token: str = Header(None)):
    """Used for daemon-to-control-plane auth"""
    expected_token = os.getenv("SYLK_TOKEN", "default-dev-token")
    if x_sylk_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid X-Sylk-Token")
    return x_sylk_token

def verify_user_session(authorization: str = Header(None)):
    """Used for frontend-to-control-plane user session auth"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split(" ")[1]
    email = r.get(f"session:{token}")
    if not email:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return email.decode("utf-8")

# --- Auth Endpoints (Frontend API) ---
@router.post("/auth/signup")
async def signup(user: auth.UserCreate):
    success = auth.create_user(user)
    if not success:
        raise HTTPException(status_code=400, detail="Email already registered")
    return {"message": "User created successfully"}

@router.post("/auth/login")
async def login(user: auth.UserLogin):
    db_user = auth.get_user_by_email(user.email)
    if not db_user or not auth.verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate session token
    token = str(uuid.uuid4())
    # Session expires in 24 hours
    r.setex(f"session:{token}", 86400, db_user["email"]) 
    
    return {"token": token, "email": db_user["email"], "username": db_user["username"]}

# --- Task Endpoints (Frontend API) ---
@router.post("/tasks", response_model=schemas.TaskOut)
async def create_task(task: schemas.TaskIn, db: Session = Depends(get_db), current_user: str = Depends(verify_user_session)):
    task_id = str(uuid.uuid4())
    pref = task.hardware_pref.value if task.hardware_pref else schemas.HardwareType.DEFAULT.value

    db_task = TaskRecord(
        task_id=task_id, code=task.code, hardware_pref=pref, status=TaskStatusEnum.QUEUED
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    queue_task(task_id, task.code, pref, task.language)
    r.publish("sylk_events", json.dumps({"event": "task_queued", "task_id": task_id, "language": task.language}))
    return schemas.TaskOut(task_id=task_id, status=schemas.TaskStatus.QUEUED)

@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
async def get_task(task_id: str, db: Session = Depends(get_db), current_user: str = Depends(verify_user_session)):
    db_task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return schemas.TaskOut(
        task_id=db_task.task_id, status=schemas.TaskStatus(db_task.status.value),
        result=db_task.result, node_id=db_task.node_id, latency_ms=db_task.latency_ms
    )

# --- Node Endpoints (Internal / Daemon Hook) ---
@router.post("/register")
async def register_node(node: schemas.NodeRegister):
    # Store Node Info in Redis globally for telemetry
    r.hset(f"node:{node.node_id}", mapping={
        "hostname": node.hostname,
        "hardware_type": node.hardware_type.value,
        "cpu_cores": node.cpu_cores,
        "memory_mb": node.memory_mb,
        "last_seen": time.time(),
        "status": "idle"
    })
    return {"status": "registered"}

@router.post("/heartbeat")
async def node_heartbeat(heartbeat: schemas.NodeHeartbeat):
    node_key = f"node:{heartbeat.node_id}"
    if r.exists(node_key):
        r.hset(node_key, "last_seen", time.time())
        r.hset(node_key, "status", "busy" if heartbeat.is_busy else "idle")
        r.hset(node_key, "cpu_usage", str(heartbeat.cpu_usage))
        r.hset(node_key, "memory_usage", str(heartbeat.memory_usage))
        # Autocleanup if node goes dark for 60 seconds
        r.expire(node_key, 60)
    return {"status": "alive"}

# --- Data Endpoints (Frontend API) ---
@router.get("/nodes")
async def get_nodes(current_user: str = Depends(verify_user_session)):
    keys = r.keys("node:*")
    nodes = []
    for k in keys:
        node_data = r.hgetall(k)
        nodes.append({
            "id": k.decode("utf-8").split(":")[1],
            "status": node_data.get(b"status", b"unknown").decode("utf-8"),
            "hardware_type": node_data.get(b"hardware_type", b"unknown").decode("utf-8"),
            "cpu_usage": float(node_data.get(b"cpu_usage", 0)),
            "memory_usage": float(node_data.get(b"memory_usage", 0))
        })
    return {"nodes": nodes}

@router.get("/analytics/stats")
async def get_analytics(db: Session = Depends(get_db), current_user: str = Depends(verify_user_session)):
    total_tasks = db.query(TaskRecord).count()
    failed_tasks = db.query(TaskRecord).filter(TaskRecord.status == TaskStatusEnum.FAILED).count()
    success_tasks = db.query(TaskRecord).filter(TaskRecord.status == TaskStatusEnum.DONE).count()
    
    error_rate = 0
    if total_tasks > 0:
        error_rate = (failed_tasks / total_tasks) * 100
        
    avg_latency = db.query(func.avg(TaskRecord.latency_ms)).filter(TaskRecord.latency_ms.isnot(None)).scalar() or 0
    
    return {
        "total": total_tasks,
        "success": success_tasks,
        "failed": failed_tasks,
        "error_rate_pct": round(error_rate, 2),
        "avg_latency_ms": round(avg_latency, 2)
    }

@router.get("/telemetry")
async def get_telemetry(request: Request):
    # SSE does not natively support custom headers in all browsers (like Bearer tokens).
    # Typically this is handled via a URL token query param.
    # We will enforce token validation if 'token' is provided in query params.
    token = request.query_params.get("token")
    if not token or not r.get(f"session:{token}"):
        raise HTTPException(status_code=401, detail="Invalid token for SSE channel")

    async def event_generator():
        pubsub = r.pubsub()
        pubsub.subscribe("sylk_events")
        
        last_nodes_poll = 0
        while True:
            if await request.is_disconnected():
                pubsub.unsubscribe("sylk_events")
                pubsub.close()
                break

            # Poll for pubsub messages
            message = pubsub.get_message(ignore_subscribe_messages=True)
            if message and message.get('type') == 'message':
                event_data = json.loads(message['data'].decode('utf-8'))
                yield {
                    "event": "sylk_event",
                    "data": json.dumps(event_data)
                }

            # Poll for node status every 2 seconds
            if time.time() - last_nodes_poll > 2:
                last_nodes_poll = time.time()
                keys = r.keys("node:*")
                nodes = []
                for k in keys:
                    status = r.hget(k, "status")
                    node_id = k.decode("utf-8").split(":")[1]
                    nodes.append({"id": node_id, "status": status.decode("utf-8") if status else "unknown"})

                data = {
                    "timestamp": time.time(),
                    "nodes": nodes
                }
                yield {
                    "event": "telemetry",
                    "id": "message_id",
                    "retry": 15000,
                    "data": json.dumps(data)
                }
            
            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())
