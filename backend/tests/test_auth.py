from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException

from app.auth import get_current_user, get_current_user_email
from app.models import User


async def test_get_current_user_recovers_from_duplicate_insert_race():
    existing_user = User(email="dev-user@gmail.com")
    first_result = SimpleNamespace(first=lambda: None)
    second_result = SimpleNamespace(first=lambda: existing_user)
    session = SimpleNamespace(
        add=Mock(),
        exec=AsyncMock(side_effect=[first_result, second_result]),
        commit=AsyncMock(
        side_effect=IntegrityError("INSERT INTO users ...", params=None, orig=Exception("duplicate"))
        ),
        rollback=AsyncMock(),
    )

    user = await get_current_user(email="dev-user@gmail.com", session=session)

    assert user is existing_user
    assert session.add.call_count == 1
    session.rollback.assert_awaited_once()
    assert session.exec.await_count == 2


def test_get_current_user_email_uses_explicit_dev_email():
    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("DEV_USER_EMAIL", "seeded@example.com")
        email = get_current_user_email(request=request, x_goog_authenticated_user_email=None)

    assert email == "seeded@example.com"
    assert request.state.auth_source == "local_dev_env"


def test_get_current_user_email_requires_explicit_local_email():
    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
        with pytest.raises(HTTPException, match="DEV_USER_EMAIL"):
            get_current_user_email(request=request, x_goog_authenticated_user_email=None)
