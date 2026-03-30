from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum

class HardwareType(str, Enum):
    X86 = "x86"
    ARM = "arm"
    GPU = "gpu"

class TaskStatus(str, Enum):
    QUEUED = "queued"
    PULLED = "pulled"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"

class TaskIn(BaseModel):
    code: str
    language: str = "python"
    hardware_pref: Optional[HardwareType] = HardwareType.X86

class TaskOut(BaseModel):
    task_id: str
    status: TaskStatus
    result: Optional[str] = None
    node_id: Optional[str] = None
    latency_ms: Optional[float] = None

class NodeRegister(BaseModel):
    node_id: str
    hostname: str
    hardware_type: HardwareType
    cpu_cores: int
    memory_mb: int

class NodeHeartbeat(BaseModel):
    node_id: str
    cpu_usage: float
    memory_usage: float
    is_busy: bool
