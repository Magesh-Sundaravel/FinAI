import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import expenses, agent

app = FastAPI(
    title="Finance AI Agents API",
    description="Backend API for parsing spreadsheets, categorizing expenses, and running AI financial agents.",
    version="0.1.0",
)

# Enable CORS for the React/Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
