import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

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

# API Routes
app.include_router(routes.router)

# Mount Static Frontend
# Note: Mount after router so API paths take precedence
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.on_event("startup")
async def startup_event():
    # Start the fallback monitor background task
    asyncio.create_task(fallback_monitor())


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/{path:path}")
async def catch_all(path: str):
    # Serve static HTML files without extension if requested, or fallback to file
    file_path = os.path.join("frontend", path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    # If it looks like a page (no extension), try adding .html
    if "." not in path:
        html_path = f"{file_path}.html"
        if os.path.exists(html_path):
            return FileResponse(html_path)
    return FileResponse("frontend/index.html")
