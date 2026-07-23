"""Module C — FastAPI API Gateway for IndusMind.

Routes requests to Module A (Prediction Engine) and Module B
(Agent Engine). Pushes real-time updates to the frontend via WebSocket.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.middleware.auth import AuthMiddleware
from api.routers import gateway, ws, history
from api.services.proxy import ProxyService
from api.services.ws_manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: initialize services and store on app.state."""
    # Startup
    proxy = ProxyService()
    ws_manager = ConnectionManager()
    await proxy.startup()
    history_store = history.HistoryStore(settings.history_file)
    await history_store.load()
    app.state.proxy = proxy
    app.state.ws_manager = ws_manager
    app.state.history_store = history_store
    ws.manager = ws_manager  # inject into ws router
    yield
    # Shutdown
    await proxy.shutdown()


app = FastAPI(
    title="IndusMind Gateway",
    description="Module C — API Gateway (routing + WebSocket push)",
    version="0.2.0",
    lifespan=lifespan,
)

# Default service instances (lifespan replaces these on startup)
app.state.proxy = ProxyService()
app.state.ws_manager = ConnectionManager()
app.state.history_store = history.HistoryStore(settings.history_file)
ws.manager = app.state.ws_manager

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth
app.add_middleware(AuthMiddleware)

# Routes
app.include_router(history.router)
app.include_router(gateway.router)
app.include_router(ws.router)


@app.get("/health")
async def health_check():
    """Readiness probe for docker-compose."""
    return {"status": "ok", "service": "module-c-gateway"}
