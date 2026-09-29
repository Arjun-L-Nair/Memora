"""
database/base.py

Defines the SQLAlchemy 2.0 declarative base.

Every ORM model in this application (via models/base_model.py) ultimately
inherits from this `Base` class. SQLAlchemy uses it to:
    - Collect table metadata (Base.metadata) for all mapped models.
    - Provide the mapper registry required for relationship resolution.

Alembic's `env.py` will import `Base.metadata` from this file to enable
autogenerate migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Root declarative base class for all ORM models.

    This class intentionally contains no columns or logic.
    It exists purely as the shared metadata/registry anchor point.
    """
    pass
