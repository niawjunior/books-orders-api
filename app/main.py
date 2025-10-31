from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.middleware_tenant import TenantMiddleware
from app.core.middleware_correlation import CorrelationIdMiddleware
from app.core.logging import setup_logging
from app.core.errors import register_exception_handlers


# Routers
from fastapi import APIRouter
from app.api.routes.tenants import router as tenants_router
from app.api.routes.authors import router as authors_router
from app.api.routes.books import router as books_router
from app.api.routes.orders import router as orders_router


setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Books Orders API - A multi-tenant API for managing books, authors, and orders.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",

)

# CORS middleware - allow docs UI to make API requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares
app.add_middleware(TenantMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# Root endpoint
@app.get("/")
async def root():
    """API root endpoint with basic information."""
    return {
        "message": "Welcome to Books Orders API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "api_v1_str": settings.API_V1_STR,
        "endpoints": {
            "tenants": f"{settings.API_V1_STR}/tenants",
            "authors": f"{settings.API_V1_STR}/authors",
            "books": f"{settings.API_V1_STR}/books",
            "orders": f"{settings.API_V1_STR}/orders",
        },

        "authentication": {
            "type": "None required for docs, tenant-based for API",
            "docs_access": "No X-Tenant header needed",
            "api_access": "X-Tenant header required"
        }
    }

register_exception_handlers(app)

# Mount routers
api = APIRouter(prefix=settings.API_V1_STR)
api.include_router(tenants_router)
api.include_router(authors_router)
api.include_router(books_router)
api.include_router(orders_router)
app.include_router(api)

register_exception_handlers(app)
