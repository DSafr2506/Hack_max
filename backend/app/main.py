import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import logic, maxapi
from app.admin import router as admin_router
from app.api import router
from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx пишет URL, а в URL бывают user_id
log = logging.getLogger("app")


def seed_if_empty() -> None:
    from app import seed

    db = SessionLocal()
    try:
        if not db.scalar(select(func.count(Event.id))):
            created, _ = seed.seed(db, seed.load_events())
            log.info("первый запуск: загружено мероприятий из events.yaml: %s", created)
    except Exception:
        log.exception("не удалось загрузить events.yaml")
    finally:
        db.close()


def create_app(start_background: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db()
        if settings.seed_if_empty:
            seed_if_empty()
        scheduler = poller = None
        if start_background:
            scheduler = BackgroundScheduler(timezone="UTC")
            scheduler.add_job(logic.run_dispatch_job, "interval", seconds=30, max_instances=1, coalesce=True)
            scheduler.start()
            if settings.max_mode == "webhook":
                scheduler.add_job(maxapi.ensure_webhook, "interval", minutes=30, max_instances=1)
            poller = maxapi.start_bot(logic.handle_update)
        yield
        if poller:
            poller.stop()
        if scheduler:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="Агрегатор возможностей — backend", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
        return JSONResponse({"error": {**detail, "details": {}}}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "validation_error", "message": "invalid request", "details": {"errors": jsonable_encoder(exc.errors())}}},
            status_code=422,
        )

    @app.get("/health")
    def health() -> dict:
        db = SessionLocal()
        try:
            count = db.scalar(select(func.count(Event.id)))
        finally:
            db.close()
        return {"status": "ok", "events": count, "bot": maxapi.BOT_INFO.get("username")}

    app.include_router(router)
    app.include_router(admin_router)
    return app


app = create_app()
