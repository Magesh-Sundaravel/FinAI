# ruff: noqa: E402
import os
from pathlib import Path

# Load .env file if it exists in the backend root
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from sqlmodel import SQLModel, create_engine, Session, text

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to local SQLite database in the backend/data directory
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "expenses.db")
    DATABASE_URL = f"sqlite:///{db_path}"

# For SQLite, connect_args={"check_same_thread": False} is required
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)

def init_db():
    # Import models here to make sure they are registered on SQLModel.metadata before creation
    from app.models import Expense, User  # noqa: F401
    SQLModel.metadata.create_all(engine)
    
    # Run migrations to add missing columns to existing tables
    with Session(engine) as session:
        # Check if user_id column exists in expenses table
        if engine.dialect.name == "postgresql":
            # For PostgreSQL (Production Cloud SQL)
            check_sql = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='expenses' AND column_name='user_id';
            """
            res = session.execute(text(check_sql)).first()
            if not res:
                print("Migration: Adding user_id column to expenses table (PostgreSQL)...")
                session.execute(text("ALTER TABLE expenses ADD COLUMN user_id UUID REFERENCES users(id);"))
                session.commit()
        elif engine.dialect.name == "sqlite":
            # For SQLite (Local Sandbox)
            res = session.execute(text("PRAGMA table_info(expenses);")).all()
            columns = [row[1] for row in res]
            if "user_id" not in columns:
                print("Migration: Adding user_id column to expenses table (SQLite)...")
                session.execute(text("ALTER TABLE expenses ADD COLUMN user_id TEXT REFERENCES users(id);"))
                session.commit()

def get_session():
    with Session(engine) as session:
        yield session
