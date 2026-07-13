from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.errors import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(_request: Request, error: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=int(error.status_code),
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    def handle_request_validation_error(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed",
                    "fields": error.errors(),
                }
            },
        )

    @app.exception_handler(ValidationError)
    def handle_validation_error(
        _request: Request,
        error: ValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Validation failed",
                    "fields": error.errors(),
                }
            },
        )
