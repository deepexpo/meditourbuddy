from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.errors import AppError
from app.mcp_client import mcp_manager
from app.routers import analytics, auth, cases, clinics, mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the MCP connection once, reuse it for every request.
    await mcp_manager.connect()
    yield
    await mcp_manager.disconnect()
    await engine.dispose()


app = FastAPI(title="MediTourBuddy Gateway", lifespan=lifespan)

# Same API serves the iOS app and any future web app — lock this down to
# your real domains before going live.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code, **exc.extra},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": "http_error"})


app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(mcp.router)
app.include_router(clinics.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    mcp_connected = mcp_manager.session is not None
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_connected = True
    except Exception:  # noqa: BLE001 - health check should never raise
        db_connected = False
    return {"status": "ok", "mcp_connected": mcp_connected, "db_connected": db_connected}
