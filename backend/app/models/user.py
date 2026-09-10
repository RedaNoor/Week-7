from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.services.base import Base

class User(Base):
    """User account model.
    Stored in the same database as other entities.
    """
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_user_email"),)

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(150), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # "admin" or "user"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
