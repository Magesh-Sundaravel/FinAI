import os
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import expenses, agent
from app.db import init_db

# Load .env file if it exists in the backend root
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables (SQLite or Postgres depending on environment)
    init_db()
    yield

app = FastAPI(
    title="Finance AI Agents API",
    description="Backend API for parsing spreadsheets, categorizing expenses, and running AI financial agents.",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for the React/Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory in data folder
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
os.makedirs(uploads_dir, exist_ok=True)

# Mount static files
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

# Include routers
app.include_router(expenses.router, prefix="/api/expenses", tags=["Expenses"])
app.include_router(agent.router, prefix="/api/agent", tags=["AI Agent"])

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Finance AI Agents API!",
        "docs_url": "/docs",
        "status": "healthy"
    }

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
