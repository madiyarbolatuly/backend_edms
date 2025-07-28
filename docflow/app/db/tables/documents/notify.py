from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, String, Text, Enum, DateTime, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PGEnum


from app.db.tables.base_class import NotifyEnum
from app.db.models import Base


class Notify(Base):
    __tablename__ = "notify"

    id           = Column(UUID(as_uuid=True),
                          default=uuid4,
                          primary_key=True,
                          index=True,
                          nullable=False)
    user_id      = Column(String(26), ForeignKey("users.id"), nullable=False)
    message      = Column(Text, nullable=False)
    type = Column(PGEnum(NotifyEnum, name="notifyenum"), nullable=False)
    status       = Column(Enum(NotifyEnum), default=NotifyEnum.unread)
    created_at   = Column(DateTime(timezone=True),
                          default=datetime.now(timezone.utc),
                          nullable=False)
