# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.deps import get_db
from app.db.session import engine
from app.db.mixins import Base
import app.db.models 
# ✅ CRITICAL: load DB models so Base.metadata is populated
import app.db.models  # noqa: F401

# Routers
from app.api.v1.users import router as users_router
from app.api.v1.agencies import router as agencies_router
from app.api.v1.auth import router as auth_router
from app.web.routes import router as ui_router
from app.web.routes_media import router as media_router
from app.web.routes_admin import router as admin_router

app = FastAPI(title=settings.APP_NAME)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    print("✅ create_all done. Tables:", list(Base.metadata.tables.keys()))

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    same_site="lax",
    https_only=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# Routers
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(users_router, prefix="/api/v1", tags=["users"])
app.include_router(agencies_router, prefix="/api/v1", tags=["agencies"])
app.include_router(ui_router)
app.include_router(media_router)
app.include_router(admin_router)

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/debug/db-ping")
def db_ping(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"db": "ok"}

@app.get("/debug/models")
def models_loaded():
    return sorted(Base.metadata.tables.keys())
