"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SELECT 1")
    # Tables are created from SQLAlchemy metadata for portability across SQLite tests and PostgreSQL.
    from app.models import Base
    from sqlalchemy import create_engine
    from app.config import get_settings

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
