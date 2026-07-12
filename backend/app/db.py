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

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, text
from sqlmodel.ext.asyncio.session import AsyncSession


def _to_async_url(url: str) -> str:
    """
    Normalize a plain sqlite:// or postgresql:// URL to its async-driver form.
    """
    if url.startswith("sqlite+aiosqlite://") or url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to local SQLite database in the backend/data directory
    db_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "expenses.db")
    DATABASE_URL = f"sqlite:///{db_path}"

engine: AsyncEngine = create_async_engine(_to_async_url(DATABASE_URL), echo=True)

# Read-only engine for chatbot Text-to-SQL operations
READONLY_DATABASE_URL = os.environ.get("READONLY_DATABASE_URL") or DATABASE_URL
readonly_engine: AsyncEngine = create_async_engine(_to_async_url(READONLY_DATABASE_URL), echo=True)

# Session factories usable outside of FastAPI's Depends() (e.g. LangGraph tool nodes)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
AsyncReadonlySessionLocal = async_sessionmaker(readonly_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    # Import models here to make sure they are registered on SQLModel.metadata before creation
    from app.models import Expense, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

        # Run migrations to add missing columns to existing tables
        if engine.dialect.name == "postgresql":
            # For PostgreSQL (Production Cloud SQL)
            check_sql = """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='expenses' AND column_name='user_id';
            """
            res = (await conn.execute(text(check_sql))).first()
            if not res:
                print("Migration: Adding user_id column to expenses table (PostgreSQL)...")
                await conn.execute(text("ALTER TABLE expenses ADD COLUMN user_id UUID REFERENCES users(id);"))
        elif engine.dialect.name == "sqlite":
            # For SQLite (Local Sandbox)
            res = (await conn.execute(text("PRAGMA table_info(expenses);"))).all()
            columns = [row[1] for row in res]
            if "user_id" not in columns:
                print("Migration: Adding user_id column to expenses table (SQLite)...")
                await conn.execute(text("ALTER TABLE expenses ADD COLUMN user_id TEXT REFERENCES users(id);"))


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


async def get_readonly_session():
    async with AsyncReadonlySessionLocal() as session:
        yield session
