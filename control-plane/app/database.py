from sqlalchemy import create_engine, Column, String, Float, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum
import datetime

import os

_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(_data_dir, exist_ok=True)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(_data_dir, 'sylk_analytics.db')}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class TaskStatusEnum(str, enum.Enum):
    QUEUED = "queued"
    PULLED = "pulled"
    EXECUTING = "executing"
    DONE = "done"
    FAILED = "failed"

class FunctionRecord(Base):
    __tablename__ = "functions"

    function_id = Column(String, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    language = Column(String, nullable=False)  # "python" or "node"
    code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class TaskRecord(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    function_id = Column(String, ForeignKey("functions.function_id"), nullable=True)
    code = Column(String)
    hardware_pref = Column(String)
    status = Column(SQLEnum(TaskStatusEnum), default=TaskStatusEnum.QUEUED)
    result = Column(String, nullable=True)
    node_id = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    simulated_cost = Column(Float, default=0.0)

# Create tables
Base.metadata.create_all(bind=engine)
