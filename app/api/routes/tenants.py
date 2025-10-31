from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.session import engine
from app.models.base import Base
from starlette.status import (
    HTTP_400_BAD_REQUEST,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/{tenant}/bootstrap")
def bootstrap_tenant(tenant: str):
    # Allow alphanumeric, hyphens, and underscores (common in tenant names)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', tenant):
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid tenant name")
    if not tenant or len(tenant) > 63:
        raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Tenant name must be 1-63 characters")

    with engine.begin() as conn:
        _ = conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{tenant}"'))
        _ = conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        _ = conn.execute(text(f'SET search_path TO "{tenant}", public'))

        # Create tables without modifying global metadata
        original_schemas: dict[str, str | None] = {}
        try:
            # Backup original schemas
            for table_name, table in Base.metadata.tables.items():
                original_schemas[table_name] = table.schema
                table.schema = tenant

            Base.metadata.create_all(bind=conn)
        finally:
            # Restore original schemas
            for table_name, original_schema in original_schemas.items():
                if table_name in Base.metadata.tables:
                    Base.metadata.tables[table_name].schema = original_schema

    return {"status": "ok", "tenant": tenant}
