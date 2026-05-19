from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import Config
from backend.api.routes import router as api_router

config = Config()
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(title="Breakfast AI")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    from backend.bot.feishu import feishu_router, set_store
    app.include_router(feishu_router)
    from backend.api.routes import store as api_store
    set_store(api_store)
    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    return app


app = create_app()
