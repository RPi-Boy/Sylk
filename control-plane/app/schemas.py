from pydantic import BaseModel
from typing import Optional, Dict, Any
from enum import Enum

class HardwareType(str, Enum):
    DEFAULT = "default"
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
    hardware_pref: Optional[HardwareType] = HardwareType.DEFAULT

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
    name: Optional[str] = None

class NodeHeartbeat(BaseModel):
    node_id: str
    name: Optional[str] = None
    cpu_usage: float
    memory_usage: float
    is_busy: bool
    containers_running: int = 0
    max_containers: int = 10
    avg_cold_start_ms: Optional[float] = None
    avg_warm_start_ms: Optional[float] = None

# --- FaaS Schemas ---

class FunctionCreate(BaseModel):
    slug: str
    language: str  # "python" or "node"
    code: str

class FunctionOut(BaseModel):
    function_id: str
    slug: str
    language: str
    endpoint: str
    created_at: Optional[str] = None

class FunctionInvoke(BaseModel):
    params: Optional[Dict[str, Any]] = {}

class TaskResultCallback(BaseModel):
    task_id: str
    result: str
    node_id: str
    status: str = "done"  # "done" or "failed"
    latency_ms: Optional[float] = None
