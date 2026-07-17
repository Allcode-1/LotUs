import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.errors import AppError


logger = logging.getLogger(__name__)


def request_log_extra(request: Request) -> dict[str, object]:
    return {
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else None,
    }


def app_error_log_level(status_code: int) -> int:
    if status_code >= 500:
        return logging.ERROR

    if status_code in {
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.TOO_MANY_REQUESTS,
    }:
        return logging.WARNING

    return logging.INFO


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        logger.log(
            app_error_log_level(int(error.status_code)),
            "application error",
            extra={
                "event": "app_error",
                "error_code": error.code,
                "status_code": int(error.status_code),
                **request_log_extra(request),
            },
        )
        return JSONResponse(
            status_code=int(error.status_code),
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                }
            },
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    def handle_request_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        logger.info(
            "request validation error",
            extra={
                "event": "request_validation_error",
                "error_count": len(error.errors()),
                "status_code": 422,
                **request_log_extra(request),
            },
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "request_validation_error",
                        "message": "Request validation failed",
                        "fields": error.errors(),
                    }
                }
            ),
        )

    @app.exception_handler(ValidationError)
    def handle_validation_error(
        request: Request,
        error: ValidationError,
    ) -> JSONResponse:
        logger.warning(
            "response validation error",
            extra={
                "event": "validation_error",
                "error_count": len(error.errors()),
                "status_code": 422,
                **request_log_extra(request),
            },
        )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Validation failed",
                        "fields": error.errors(),
                    }
                }
            ),
        )

    @app.exception_handler(Exception)
    def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        logger.exception(
            "unhandled exception",
            extra={
                "event": "unhandled_exception",
                "status_code": 500,
                "error_type": type(error).__name__,
                **request_log_extra(request),
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "Internal server error",
                }
            },
        )
