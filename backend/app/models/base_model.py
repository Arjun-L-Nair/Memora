"""
models/base_model.py

Defines the reusable abstract BaseModel that all domain models inherit from.

This class is NOT a table itself (`__abstract__ = True`). Instead, it
contributes three common columns to every model that inherits it:

    - id:         Primary key, autoincrementing integer.
    - created_at: Timestamp set once, automatically, on row insert.
    - updated_at: Timestamp automatically refreshed on every row update.

Using an abstract base (rather than a real "base table") keeps every
domain table normalized and avoids repeating boilerplate columns in
each individual model file.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class BaseModel(Base):
    """
    Abstract base class providing shared primary key and timestamp columns.

    All domain models (Teacher, Student, LearningPlan, etc.) inherit from
    this class instead of `Base` directly.
    """

    __abstract__ = True

    # Primary key shared by every table in the system.
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    # Set once automatically by the database when a row is first inserted.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    # Automatically refreshed by SQLAlchemy whenever the row is updated.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
