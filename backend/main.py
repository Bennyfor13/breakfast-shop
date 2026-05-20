from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
    from backend.bot.feishu import feishu_router, set_store, set_feishu_credentials, set_llm_config
    app.include_router(feishu_router)
    from backend.api.routes import store as api_store
    set_store(api_store)
    set_feishu_credentials(config.feishu_app_id, config.feishu_app_secret)
    set_llm_config(config.llm_api_key, config.llm_api_url)

    # Initialize scheduler
    from backend.scheduler import init_scheduler, shutdown_scheduler
    from backend.bot.feishu import _get_tenant_access_token

    @app.on_event("startup")
    async def on_startup():
        init_scheduler(api_store, _get_tenant_access_token)

    @app.on_event("shutdown")
    async def on_shutdown():
        shutdown_scheduler()

    # Feishu custom page routes — serve SPA with tab pre-selected
    tabs = ["schedule", "payroll", "inventory", "pricing"]
    index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    for tab in tabs:
        def _make_handler(tab_name: str = tab):
            async def handler():
                injected = f'<script>window.INITIAL_TAB = "{tab_name}";</script>'
                html = index_html.replace(
                    '<script src="/app.js"></script>',
                    f'{injected}\n  <script src="/app.js"></script>',
                )
                return HTMLResponse(content=html)
            return handler
        app.get(f"/app/{tab}")(_make_handler(tab))

    if FRONTEND_DIR.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    return app


app = create_app()
