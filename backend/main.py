"""
AgentFund API - Main FastAPI Application

An AI-native trading platform where users create and manage
a team of autonomous trading agents.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from api import auth, agents, broker, market, reports, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    settings = get_settings()
    print(f"Starting {settings.app_name}...")
    yield
    # Shutdown
    print("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-native trading platform with autonomous trading agents",
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
    app.include_router(broker.router, prefix="/api/broker", tags=["Broker"])
    app.include_router(market.router, prefix="/api/market", tags=["Market Data"])
    app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
    app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": settings.api_version}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
