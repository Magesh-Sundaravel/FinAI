import os
from sqlmodel import SQLModel, create_engine, Session

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
    from app.models import Expense
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
