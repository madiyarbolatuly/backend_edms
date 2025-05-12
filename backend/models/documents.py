from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
import enum
from database import Base
from datetime import datetime

class DocumentStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    published = "published"
    archived = "archived"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    document_number = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    status = Column(Enum(DocumentStatus), nullable=False)
    media_path = Column(String)
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
