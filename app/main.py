from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.admin import router as admin_router
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router


def create_app() -> FastAPI:
    """Initialize and configure FastAPI application."""
    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Id"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
