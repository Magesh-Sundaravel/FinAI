import datetime
import uuid
from typing import Optional
from sqlmodel import SQLModel, Field, Column, DateTime


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, index=True, nullable=False
    )
    date: datetime.date = Field(index=True)
    season: str = Field(index=True)  # "Winter", "Spring", "Summer", "Autumn"
    description: str = Field(index=True)
    category: str = Field(index=True)
    amount: float
    bill_image_url: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
        ),
    )
