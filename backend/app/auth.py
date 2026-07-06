import os
from typing import Optional
from fastapi import Header, Depends
from sqlmodel import Session, select
from app.db import get_session
from app.models import User

def get_current_user_email(
    x_goog_authenticated_user_email: Optional[str] = Header(None, alias="X-Goog-Authenticated-User-Email")
) -> str:
    """
    Extract the email of the authenticated user from the Google IAP header.
    Falls back to a default email in local development environment.
    """
    if not x_goog_authenticated_user_email:
        # Default user email for local environment
        return os.environ.get("DEV_USER_EMAIL", "dev-user@gmail.com")
        
    email = x_goog_authenticated_user_email
    # Strip prefix if present (e.g. "accounts.google.com:user@gmail.com" -> "user@gmail.com")
    if ":" in email:
        email = email.split(":", 1)[1]
    return email.strip()

def get_current_user(
    email: str = Depends(get_current_user_email),
    session: Session = Depends(get_session)
) -> User:
    """
    Get or create the user profile in the database based on the authenticated email.
    """
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    
    if not user:
        # Auto-create user profile on first login
        user = User(email=email)
        session.add(user)
        session.commit()
        session.refresh(user)
        
    return user
