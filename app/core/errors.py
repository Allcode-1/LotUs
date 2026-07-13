from http import HTTPStatus


class AppError(Exception):
    status_code = HTTPStatus.BAD_REQUEST
    code = "app_error"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        status_code: HTTPStatus | None = None,
    ) -> None:
        self.message = message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        super().__init__(message)


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"


class ForbiddenError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden"


class ValidationAppError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "validation_error"


class ExternalServiceError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = "external_service_error"
