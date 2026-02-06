"""
AgentFund API - Main FastAPI Application

An AI-native trading platform where users create and manage
a team of autonomous trading agents.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    agents,
    auth,
    broker,
    chat,
    llm,
    market,
    notifications,
    reports,
    websocket,
)
from config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    settings = get_settings()

    # Startup
    logger.info(f"Starting {settings.app_name}...")

    # Initialize Alpaca WebSocket stream for real-time market data
    if settings.ALPACA_API_KEY and settings.ALPACA_API_SECRET:
        try:
            from api.websocket import setup_alpaca_stream

            await setup_alpaca_stream()
            logger.info("Alpaca real-time stream initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca stream: {e}")
            logger.info(
                "Real-time data will not be available until Alpaca credentials are configured"
            )
    else:
        logger.info("Alpaca credentials not configured - real-time data disabled")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop Alpaca stream
    from data.alpaca_stream import get_stream_client

    stream_client = get_stream_client()
    if stream_client:
        await stream_client.stop()
        logger.info("Alpaca stream stopped")


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
    app.include_router(llm.router, prefix="/api/llm", tags=["LLM"])
    app.include_router(notifications.router, prefix="/api", tags=["Notifications"])
    app.include_router(websocket.router, prefix="/api", tags=["WebSocket"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": settings.api_version}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
