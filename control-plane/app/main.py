import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import routes
from .scheduler import fallback_monitor

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Sylk Control Plane")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)

@app.on_event("startup")
async def startup_event():
    # Start the fallback monitor background task
    asyncio.create_task(fallback_monitor())

@app.get("/")
@limiter.limit("5/minute")
async def root(request: Request):
    return {"message": "Sylk Control Plane is running"}
