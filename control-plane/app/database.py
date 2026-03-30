from sqlalchemy import create_engine, Column, String, Float, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

SQLALCHEMY_DATABASE_URL = "sqlite:///./tasks.db"

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

class TaskRecord(Base):
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True, index=True)
    code = Column(String)
    hardware_pref = Column(String)
    status = Column(SQLEnum(TaskStatusEnum), default=TaskStatusEnum.QUEUED)
    result = Column(String, nullable=True)
    node_id = Column(String, nullable=True)
    latency_ms = Column(Float, nullable=True)
    simulated_cost = Column(Float, default=0.0)

# Create tables
Base.metadata.create_all(bind=engine)
