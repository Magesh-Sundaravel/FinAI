import os
from typing import Optional
from fastapi import Header, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db import get_session
from app.models import User

LOCAL_DEV_AUTH_SOURCE = "local_dev_env"
IAP_AUTH_SOURCE = "google_iap"


def _normalize_email(raw_email: str) -> str:
    email = raw_email
    if ":" in email:
        email = email.split(":", 1)[1]
    return email.strip()


def _get_dev_user_email() -> Optional[str]:
    value = os.environ.get("DEV_USER_EMAIL")
    if not value:
        return None
    email = value.strip()
    return email or None


def get_current_user_email(
    request: Request,
    x_goog_authenticated_user_email: Optional[str] = Header(None, alias="X-Goog-Authenticated-User-Email")
) -> str:
    """
    Extract the email of the authenticated user from the Google IAP header.
    In local development, require an explicit DEV_USER_EMAIL instead of silently
    falling back to a hard-coded placeholder.
    """
    if x_goog_authenticated_user_email:
        request.state.auth_source = IAP_AUTH_SOURCE
        return _normalize_email(x_goog_authenticated_user_email)

    dev_user_email = _get_dev_user_email()
    if dev_user_email:
        request.state.auth_source = LOCAL_DEV_AUTH_SOURCE
        return dev_user_email

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "No authenticated user was provided. For local development, set "
            "DEV_USER_EMAIL to the same email you seeded into the local database."
        ),
    )

async def get_current_user(
    email: str = Depends(get_current_user_email),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Get or create the user profile in the database based on the authenticated email.
    """
    statement = select(User).where(User.email == email)
    result = await session.exec(statement)
    user = result.first()

    if not user:
        # Auto-create user profile on first login
        user = User(email=email)
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            # Another request created the same email between our read and write.
            await session.rollback()
            result = await session.exec(statement)
            user = result.first()
            if not user:
                raise

    return user
