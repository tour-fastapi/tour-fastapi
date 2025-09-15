from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.deps import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
# NEW: import routers
from app.api.v1.users import router as users_router
from app.api.v1.agencies import router as agencies_router
from app.api.v1.auth import router as auth_router
from app.web.routes import router as ui_router
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from app.web import routes as ui_routes
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,  # must be non-empty and stable
    same_site="lax",                 # default is fine too
    https_only=False,                # True only under HTTPS
    max_age=60 * 60 * 24 * 7,        # optional: one week
    session_cookie="tour_session",   # optional: custom cookie name
)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

app.include_router(auth_router, prefix="/api/v1")

# CORS (open now; restrict later in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

# API routers
app.include_router(users_router, prefix="/api/v1", tags=["users"])
app.include_router(agencies_router, prefix="/api/v1", tags=["agencies"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(ui_router)
app.include_router(ui_routes.router)

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/debug/db-ping")
def db_ping(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Return full error so we can see what's wrong (dev only!)
        return JSONResponse(status_code=500, content={"error": str(e), "type": e.__class__.__name__, "trace": tb})
# app/main.py
from sqlalchemy import text

@app.get("/debug/table-check")
def table_check(db: Session = Depends(get_db)):
    # These are your legacy tables
    db.execute(text("SELECT 1 FROM users LIMIT 1"))
    db.execute(text("SELECT 1 FROM agencies LIMIT 1"))
    db.execute(text("SELECT 1 FROM packages LIMIT 1"))
    db.execute(text("SELECT 1 FROM inquiries LIMIT 1"))
    return {"tables": "ok"}

@app.get("/debug/models")
def models_loaded():
    return {"models": sorted({t.name for t in Base.metadata.tables.values()})}
# app/main.py
from app.core.config import settings

@app.get("/debug/config")
def debug_config():
    # Don’t keep this in production; just for today.
    return {"database_url": settings.DATABASE_URL}

# mount API v1
app.include_router(users_router, prefix="/api/v1")
app.include_router(agencies_router, prefix="/api/v1")
