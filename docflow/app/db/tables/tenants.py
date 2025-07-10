from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime
from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False)
    created_at  = Column(DateTime(timezone=True),
                         nullable=False,
                         default=datetime.now(timezone.utc))
