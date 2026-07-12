import datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Expense


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def other_user_id():
    return uuid.uuid4()


@pytest.fixture
async def seeded_expenses(session_factory, user_id, other_user_id):
    """
    Seed a mix of expenses for two users so tests can verify user_id isolation.
    """
    rows = [
        Expense(
            date=datetime.date(2025, 1, 10),
            season="Winter",
            description="Esselunga",
            category="Groceries",
            amount=50.0,
            user_id=user_id,
        ),
        Expense(
            date=datetime.date(2025, 1, 20),
            season="Winter",
            description="Conad",
            category="Groceries",
            amount=30.0,
            user_id=user_id,
        ),
        Expense(
            date=datetime.date(2025, 6, 5),
            season="Summer",
            description="Enel",
            category="Electricity",
            amount=80.0,
            user_id=user_id,
        ),
        Expense(
            date=datetime.date(2025, 6, 15),
            season="Summer",
            description="Esselunga",
            category="Groceries",
            amount=999.0,
            user_id=other_user_id,
        ),
    ]
    async with session_factory() as session:
        for row in rows:
            session.add(row)
        await session.commit()
    return rows


@pytest.fixture(autouse=True)
def patch_readonly_db(monkeypatch, test_engine, session_factory):
    """
    app/agent/tools.py talks to the readonly engine/sessionmaker imported at
    module load time from app.db; point those names at the isolated
    in-memory test database instead of the real one.
    """
    monkeypatch.setattr("app.agent.tools.readonly_engine", test_engine)
    monkeypatch.setattr("app.agent.tools.AsyncReadonlySessionLocal", session_factory)
