from sqlalchemy import Boolean, Column, String, ForeignKey, Enum, ARRAY, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum as PyEnum

from .base import BaseModel


# Association Table (Many-to-Many)
user_tenants = Table(
    "user_tenants",
    BaseModel.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True),
)


class UserRoles(PyEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Users(BaseModel):
    __tablename__ = "users"

    workspaces = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    active_workspace = Column(
        UUID(as_uuid=True),
        nullable=False,
    )
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRoles), name="user_roles", default=UserRoles.VIEWER)

    # Relationships
    knowledge_articles = relationship(
        "KnowledgeArticles",
        back_populates="author",
    )

    tenants = relationship("Tenants", secondary="user_tenants", back_populates="users")

    # Utility Methods
    def set_active_workspace(self, workspace_id):
        """Set the active workspace for the user."""
        if workspace_id in self.workspaces:
            self.active_workspace = workspace_id
        else:
            raise ValueError("Workspace ID is not associated with this user.")

    def add_workspace(self, workspace_id):
        """Add a new workspace to the user's list."""
        if workspace_id not in self.workspaces:
            self.workspaces.append(workspace_id)

    def remove_workspace(self, workspace_id):
        """Remove a workspace from the user's list."""
        if workspace_id in self.workspaces:
            self.workspaces.remove(workspace_id)
            # Reset active workspace if the removed workspace was active
            if self.active_workspace == workspace_id:
                self.active_workspace = self.workspaces[0] if self.workspaces else None
        else:
            raise ValueError("Workspace ID is not associated with this user.")
