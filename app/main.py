from fastapi import FastAPI

from app.api.openapi import setup_openapi
from app.api.v1.router import v1_router
from app.core.exception_handlers import register_exception_handlers


app = FastAPI(title="LotUs API")

app.include_router(v1_router)
register_exception_handlers(app)
setup_openapi(app)


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
