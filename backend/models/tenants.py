from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class Tenants(BaseModel):
    __tablename__ = "tenants"

    name = Column(String, unique=True, nullable=False)
    owner = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    description = Column(String, nullable=True)

    # Many-to-Many with Users
    users = relationship("Users", secondary="user_tenants", back_populates="tenants")

    # One-to-Many with Articles
    knowledge_articles = relationship(
        "KnowledgeArticles", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Tenant('{self.name}', {self.id})"
