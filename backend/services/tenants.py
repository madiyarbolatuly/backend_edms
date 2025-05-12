from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from ..models import Tenants
from ..schemas import TenantUpdateSchema
from . import create_tenant as create_permitio_tenant


class TenantService:

    @staticmethod
    def get_tenant_by_id(db: Session, tenant_id: UUID):
        tenant = Tenants.get_by_id(db, tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
            )
        return tenant

    @staticmethod
    async def create_tenant(db: Session, tenant_data: dict):

        new_tenant = Tenants(
            name=tenant_data["name"],
            description=tenant_data["description"],
            owner=tenant_data["owner"],
        )
        new_tenant.add(new_tenant, db)
        new_tenant.save(db)

        await create_permitio_tenant(
            new_tenant.name, str(new_tenant.id), new_tenant.description
        )
        return new_tenant

    @staticmethod
    def update_tenant(db: Session, update_obj: TenantUpdateSchema, tenant_id: UUID):
        tenant = TenantService.get_tenant_by_id(db, tenant_id)
        tenant.update(db, name=update_obj.name, description=update_obj.description)
        return tenant
