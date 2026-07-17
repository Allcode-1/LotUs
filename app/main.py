from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.openapi import setup_openapi
from app.api.v1.router import v1_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.ws.pubsub import auction_pubsub_listener


configure_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await auction_pubsub_listener.start()
    try:
        yield
    finally:
        await auction_pubsub_listener.stop()


app = FastAPI(title="LotUs API", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(v1_router)
register_exception_handlers(app)
setup_openapi(app)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
