from http import HTTPStatus
from typing import Mapping


class AppError(Exception):
    status_code = HTTPStatus.BAD_REQUEST
    code = "app_error"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: HTTPStatus | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.headers = dict(headers or {})
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "unauthorized"


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"


class ForbiddenError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden"


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"


class ValidationAppError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "validation_error"


class TooManyRequestsError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "too_many_requests"


class ServiceUnavailableError(AppError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "service_unavailable"


class ExternalServiceError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = "external_service_error"
