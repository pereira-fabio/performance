import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings
from backend.app.core.database import engine, Base, ensure_schema
from backend.app.core.migrations import migrate_to_accounts
# Import models to ensure they are registered with Base.metadata
from backend.app.models import models
from backend.app.api import (
    auth, admin, coach, connections, sync, activities, metrics, settings as settings_api,
)

# Create database tables automatically with SMB fallback
def ensure_administrator():
    """
    Guarantee somebody can administer this server.

    The rule that the first account becomes administrator only applies at
    registration, so an install whose accounts predate that rule ends up with
    nobody able to manage it -- and no way to fix that from the interface. The
    earliest account is promoted instead, which is the one that claimed the
    existing history.
    """
    from backend.app.core.database import SessionLocal
    from backend.app.models.models import User

    db = SessionLocal()
    try:
        if db.query(User).filter(User.is_admin.is_(True), User.is_active.is_(True)).count():
            return
        first = db.query(User).order_by(User.created_at.asc()).first()
        if first:
            first.is_admin = True
            db.commit()
            print(f"👑 No administrator found; promoted '{first.username}'.", flush=True)
    except Exception as exc:
        print(f"⚠️ Could not verify an administrator exists: {exc}", flush=True)
    finally:
        db.close()


def _prepare(eng):
    """Restructure before SQLAlchemy inspects, then create what is missing."""
    url = str(eng.url)
    if url.startswith("sqlite"):
        path = url.replace("sqlite:///", "")
        if path:
            migrate_to_accounts(path)
    Base.metadata.create_all(bind=eng)
    ensure_schema(eng)
    ensure_administrator()


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
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(connections.router, prefix=settings.API_V1_STR)
app.include_router(coach.router, prefix=settings.API_V1_STR)
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
