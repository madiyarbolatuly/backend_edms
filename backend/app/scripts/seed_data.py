#!/usr/bin/env python3
"""
Script to seed initial tenants and departments data.
Run this after the database is set up and migrations are applied.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.tables.tenants import Tenant
from app.db.tables.departments import Department
from app.core.config import settings

async def seed_data():
    """Seed initial tenants and departments data."""
    
    # Create async engine
    engine = create_async_engine(settings.async_database_url, echo=True)
    
    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Create initial tenants
            tenants_data = [
                {"name": "Main Organization"},
                {"name": "Development Team"},
                {"name": "Marketing Department"},
                {"name": "Human Resources"},
                {"name": "Finance Department"},
            ]
            
            tenants = []
            for tenant_data in tenants_data:
                tenant = Tenant(**tenant_data)
                session.add(tenant)
                tenants.append(tenant)
            
            await session.commit()
            
            # Get tenant IDs for departments
            tenant_ids = [tenant.id for tenant in tenants]
            
            # Create departments for each tenant
            departments_data = [
                # Main Organization departments
                {"tenant_id": tenant_ids[0], "name": "Executive Office"},
                {"tenant_id": tenant_ids[0], "name": "IT Department"},
                {"tenant_id": tenant_ids[0], "name": "Operations"},
                
                # Development Team departments
                {"tenant_id": tenant_ids[1], "name": "Frontend Development"},
                {"tenant_id": tenant_ids[1], "name": "Backend Development"},
                {"tenant_id": tenant_ids[1], "name": "QA Testing"},
                {"tenant_id": tenant_ids[1], "name": "DevOps"},
                
                # Marketing Department departments
                {"tenant_id": tenant_ids[2], "name": "Digital Marketing"},
                {"tenant_id": tenant_ids[2], "name": "Content Creation"},
                {"tenant_id": tenant_ids[2], "name": "Social Media"},
                
                # Human Resources departments
                {"tenant_id": tenant_ids[3], "name": "Recruitment"},
                {"tenant_id": tenant_ids[3], "name": "Employee Relations"},
                {"tenant_id": tenant_ids[3], "name": "Training & Development"},
                
                # Finance Department departments
                {"tenant_id": tenant_ids[4], "name": "Accounting"},
                {"tenant_id": tenant_ids[4], "name": "Budget Planning"},
                {"tenant_id": tenant_ids[4], "name": "Audit"},
            ]
            
            for dept_data in departments_data:
                department = Department(**dept_data)
                session.add(department)
            
            await session.commit()
            
            print("✅ Successfully seeded tenants and departments data!")
            print(f"Created {len(tenants)} tenants and {len(departments_data)} departments")
            
        except Exception as e:
            print(f"❌ Error seeding data: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_data()) 