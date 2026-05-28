from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
import os

from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI()

    # Starlette requires allow_credentials=False when allow_origins includes "*"
    allow_origins = settings.cors_allow_origins
    allow_credentials = True
    if "*" in allow_origins or not allow_origins:
        allow_credentials = False

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Id"],
    )


    app.include_router(chat_router)
    app.include_router(admin_router, prefix="/admin")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
