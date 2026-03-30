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
from .database import SessionLocal, TaskRecord, TaskStatusEnum, FunctionRecord
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
    
    token = str(uuid.uuid4())
    r.setex(f"session:{token}", 86400, db_user["email"]) 
    
    return {"token": token, "email": db_user["email"], "username": db_user["username"]}

# --- Legacy Task Endpoints (Frontend deploy page) ---
@router.post("/tasks", response_model=schemas.TaskOut)
async def create_task(task: schemas.TaskIn, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())
    pref = task.hardware_pref.value if task.hardware_pref else schemas.HardwareType.DEFAULT.value

    db_task = TaskRecord(
        task_id=task_id, code=task.code, hardware_pref=pref, status=TaskStatusEnum.QUEUED
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    queue_task(task_id, task.code, language=task.language)
    r.publish("sylk_events", json.dumps({"event": "task_queued", "task_id": task_id, "language": task.language}))
    return schemas.TaskOut(task_id=task_id, status=schemas.TaskStatus.QUEUED)

@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    db_task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return schemas.TaskOut(
        task_id=db_task.task_id, status=schemas.TaskStatus(db_task.status.value),
        result=db_task.result, node_id=db_task.node_id, latency_ms=db_task.latency_ms
    )

# ==========================================
# FaaS API — Function Management
# ==========================================

@router.post("/functions", response_model=schemas.FunctionOut)
async def deploy_function(fn: schemas.FunctionCreate, db: Session = Depends(get_db)):
    """Deploy a new function. Creates a persistent endpoint at /fn/{slug}."""
    # Validate language
    if fn.language not in ("python", "node"):
        raise HTTPException(status_code=400, detail="Language must be 'python' or 'node'")
    
    # Validate slug uniqueness
    existing = db.query(FunctionRecord).filter(FunctionRecord.slug == fn.slug).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Function with slug '{fn.slug}' already exists")
    
    function_id = str(uuid.uuid4())
    db_fn = FunctionRecord(
        function_id=function_id,
        slug=fn.slug,
        language=fn.language,
        code=fn.code,
    )
    db.add(db_fn)
    db.commit()
    db.refresh(db_fn)

    r.publish("sylk_events", json.dumps({
        "event": "function_deployed",
        "function_id": function_id,
        "slug": fn.slug,
        "language": fn.language
    }))

    return schemas.FunctionOut(
        function_id=function_id,
        slug=fn.slug,
        language=fn.language,
        endpoint=f"/fn/{fn.slug}",
        created_at=str(db_fn.created_at)
    )

@router.get("/functions", response_model=List[schemas.FunctionOut])
async def list_functions(db: Session = Depends(get_db)):
    """List all deployed functions."""
    fns = db.query(FunctionRecord).all()
    return [
        schemas.FunctionOut(
            function_id=f.function_id,
            slug=f.slug,
            language=f.language,
            endpoint=f"/fn/{f.slug}",
            created_at=str(f.created_at)
        )
        for f in fns
    ]

@router.get("/functions/{slug}")
async def get_function(slug: str, db: Session = Depends(get_db)):
    """Get details of a deployed function by slug."""
    fn = db.query(FunctionRecord).filter(FunctionRecord.slug == slug).first()
    if not fn:
        raise HTTPException(status_code=404, detail=f"Function '{slug}' not found")
    return schemas.FunctionOut(
        function_id=fn.function_id,
        slug=fn.slug,
        language=fn.language,
        endpoint=f"/fn/{fn.slug}",
        created_at=str(fn.created_at)
    )

# ==========================================
# FaaS API — Function Invocation
# ==========================================

@router.post("/fn/{slug}")
async def invoke_function(slug: str, body: schemas.FunctionInvoke, db: Session = Depends(get_db)):
    """
    Invoke a deployed function synchronously.
    Blocks up to 30s waiting for the worker result via callback.
    """
    # 1. Look up the function
    fn = db.query(FunctionRecord).filter(FunctionRecord.slug == slug).first()
    if not fn:
        raise HTTPException(status_code=404, detail=f"Function '{slug}' not found")
    
    # 2. Create a task record
    task_id = str(uuid.uuid4())
    db_task = TaskRecord(
        task_id=task_id,
        function_id=fn.function_id,
        code=fn.code,
        hardware_pref="default",
        status=TaskStatusEnum.QUEUED
    )
    db.add(db_task)
    db.commit()

    # 3. Build callback URL (workers will POST results here)
    callback_url = f"/callback/{task_id}"

    # 4. Push to the language-specific queue
    queue_name = queue_task(
        task_id=task_id,
        code=fn.code,
        language=fn.language,
        callback_url=callback_url,
        params=body.params
    )

    r.publish("sylk_events", json.dumps({
        "event": "task_queued",
        "task_id": task_id,
        "language": fn.language,
        "slug": fn.slug
    }))

    # 5. Block waiting for result (worker will RPUSH to result_ready:{task_id})
    timeout = 30
    result_key = f"result_ready:{task_id}"
    result = r.blpop(result_key, timeout=timeout)

    if result is None:
        # Timeout — update task status
        db_task_ref = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if db_task_ref:
            db_task_ref.status = TaskStatusEnum.FAILED
            db_task_ref.result = "Timeout: No worker responded within 30s"
            db.commit()
        raise HTTPException(status_code=504, detail="Function execution timed out (30s)")

    # 6. Parse the result
    _, result_data = result
    result_payload = json.loads(result_data.decode("utf-8"))

    return {
        "task_id": task_id,
        "function": slug,
        "status": result_payload.get("status", "done"),
        "output": result_payload.get("result", ""),
        "node_id": result_payload.get("node_id", "unknown")
    }

# ==========================================
# Worker Callback Endpoint
# ==========================================

@router.post("/callback/{task_id}")
async def worker_callback(task_id: str, body: schemas.TaskResultCallback, db: Session = Depends(get_db)):
    """
    Workers POST results here after execution.
    This unblocks the /fn/{slug} handler waiting on BLPOP.
    """
    # Update task record in DB
    db_task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
    if db_task:
        db_task.status = TaskStatusEnum.DONE if body.status == "done" else TaskStatusEnum.FAILED
        db_task.result = body.result
        db_task.node_id = body.node_id
        db.commit()
    
    # Store result in Redis for backward compat
    r.set(f"result:{task_id}", body.result, ex=3600)

    # Signal the blocked invoke handler
    signal_payload = json.dumps({
        "task_id": task_id,
        "result": body.result,
        "node_id": body.node_id,
        "status": body.status
    })
    r.rpush(f"result_ready:{task_id}", signal_payload)
    # Auto-expire the signal key after 60s
    r.expire(f"result_ready:{task_id}", 60)

    # Broadcast event
    r.publish("sylk_events", json.dumps({
        "event": f"task_{'completed' if body.status == 'done' else 'failed'}",
        "task_id": task_id,
        "node_id": body.node_id
    }))

    return {"status": "received"}

# --- Node Endpoints (Internal / Daemon Hook) ---
@router.post("/register")
async def register_node(node: schemas.NodeRegister):
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
    token = request.query_params.get("token")
    # Auth removed for demo mode

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
