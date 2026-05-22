import time























import uuid
import datetime as dt
from contextlib import asynccontextmanager
from urllib.request import Request
from fastapi import FastAPI

from rag.api.context import request_id_var
from rag.api.logger_config import logger
from rag.api.routers import chat, eval, health, ingestion
from rag.db.session import engine
from prometheus_client import make_asgi_app
from rag.api.metrics import REQUEST_COUNT, REQUEST_LATENCY, ERROR_COUNT


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Simplon RAG Sample API",
        description="Sample RAG support chatbot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        req_id = str(uuid.uuid4())
        request_id_var.set(req_id)
        request.state.request_id = req_id

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        endpoint = request.url.path

        logger.info("request_processed", extra={
            "request_datetime": dt.datetime.now(),
            "request_id": req_id,
            "endpoint": endpoint,
            "method": request.method,
            "status_code": response.status_code,
            "latency": round(duration, 4),
        })

        REQUEST_COUNT.labels(
            endpoint=endpoint,
            method=request.method,
            status_code=str(response.status_code),
        ).inc()

        REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

        if response.status_code >= 400:
            ERROR_COUNT.labels(endpoint=endpoint).inc()

        response.headers["X-Request-ID"] = req_id

        return response

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(ingestion.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(eval.router, prefix="/api/v1")

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app
