import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, ensure_schema
from backend.app.core.migrations import migrate_to_accounts
# Import models to ensure they are registered with Base.metadata
from backend.app.models import models
from backend.app.api import auth, sync, activities, metrics, settings as settings_api

# Create database tables automatically with SMB fallback
def _prepare(eng):
    """Restructure before SQLAlchemy inspects, then create what is missing."""
    url = str(eng.url)
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "")
        if path:
            migrate_to_accounts(path)
    Base.metadata.create_all(bind=eng)
    ensure_schema(eng)


try:
    _prepare(engine)
except Exception as e:
    print(f"⚠️ Initial database table creation failed: {e}. Retrying with local container storage...")
    local_dir = "/app/data"
    os.makedirs(local_dir, exist_ok=True)
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{local_dir}/peakpace.db", connect_args={"check_same_thread": False})
    _prepare(engine)
    # Rebind the session factory, otherwise every request keeps using the
    # engine that just failed and the fallback database is never read.
    import backend.app.core.database as _db
    _db.engine = engine
    _db.SessionLocal.configure(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Training analytics from Health Connect: running, walking and gym."
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(sync.router, prefix=settings.API_V1_STR)
app.include_router(activities.router, prefix=settings.API_V1_STR)
app.include_router(metrics.router, prefix=settings.API_V1_STR)
app.include_router(settings_api.router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "app": settings.PROJECT_NAME,
        "version": "1.0.0"
    }

# Mount static frontend if build directory exists
frontend_dist = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
