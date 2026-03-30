from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session
from typing import List
import uuid
import os

from . import schemas
from .database import SessionLocal, TaskRecord, TaskStatusEnum
from .scheduler import queue_task

router = APIRouter()

# API Key Dependency
def verify_token(x_sylk_token: str = Header(None)):
    expected_token = os.getenv("SYLK_TOKEN", "default-dev-token")
    if x_sylk_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid X-Sylk-Token")
    return x_sylk_token

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/tasks", response_model=schemas.TaskOut)
async def create_task(request: Request, task: schemas.TaskIn, db: Session = Depends(get_db), token: str = Depends(verify_token)):
    task_id = str(uuid.uuid4())
    
    # Check Hardware Pref
    pref = task.hardware_pref.value if task.hardware_pref else schemas.HardwareType.X86.value

    # 1. Write to DB
    db_task = TaskRecord(
        task_id=task_id,
        code=task.code,
        hardware_pref=pref,
        status=TaskStatusEnum.QUEUED
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    # 2. Add to Redis
    queue_task(task_id, task.code, pref)

    return schemas.TaskOut(task_id=task_id, status=schemas.TaskStatus.QUEUED)

@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    db_task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return schemas.TaskOut(
        task_id=db_task.task_id,
        status=schemas.TaskStatus(db_task.status.value),
        result=db_task.result,
        node_id=db_task.node_id,
        latency_ms=db_task.latency_ms
    )

@router.post("/register")
async def register_node(node: schemas.NodeRegister):
    # For now, just print to console or store in Redis
    print(f"Registered Node: {node.node_id} ({node.hardware_type})")
    return {"status": "registered"}

@router.post("/heartbeat")
async def node_heartbeat(heartbeat: schemas.NodeHeartbeat):
    # Store in Redis with TTL?
    print(f"Heartbeat: {heartbeat.node_id} - Busy: {heartbeat.is_busy}")
    return {"status": "alive"}

from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import time

@router.get("/telemetry")
async def get_telemetry(request: Request):
    async def event_generator():
        while True:
            # If client closes connection, stop sending events
            if await request.is_disconnected():
                break

            # Fetch active nodes from Redis or Memory (placeholder for now)
            # In a real app we'd query Redis or DB for connected nodes & tasks
            data = {
                "timestamp": time.time(),
                "nodes": [
                    {"id": "local-node-01", "status": "idle"},
                    {"id": "rp4-01", "status": "busy"},
                ]
            }
            yield {
                "event": "telemetry",
                "id": "message_id",
                "retry": 15000,
                "data": json.dumps(data)
            }
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
