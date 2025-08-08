from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.models import Base


class Department(Base):
    __tablename__ = "departments"

    id          = Column(Integer, primary_key=True)
    tenant_id   = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name        = Column(String, nullable=False)
    created_at  = Column(DateTime(timezone=True),
                         nullable=False,
                         default=datetime.now(timezone.utc))
