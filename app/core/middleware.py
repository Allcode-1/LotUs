import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import reset_request_id, set_request_id


REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = get_or_create_request_id(request)
        token = set_request_id(request_id)
        request.state.request_id = request_id
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = get_duration_ms(started_at)
            logger.exception(
                "http request failed",
                extra={
                    "event": "http_request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "client_ip": get_client_ip(request),
                },
            )
            reset_request_id(token)
            raise

        duration_ms = get_duration_ms(started_at)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "http request completed",
            extra={
                "event": "http_request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
            },
        )
        reset_request_id(token)

        return response


def get_or_create_request_id(request: Request) -> str:
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if request_id:
        request_id = request_id.strip()
        if request_id:
            return request_id[:MAX_REQUEST_ID_LENGTH]

    return str(uuid4())


def get_duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 2)


def get_client_ip(request: Request) -> str | None:
    if request.client is None:
        return None

    return request.client.host
