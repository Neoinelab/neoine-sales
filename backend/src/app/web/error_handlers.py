"""오류를 RFC 9457 problem+json으로 바꾼다. 내부 예외 메시지는 도메인 오류만 노출한다."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.domain.common.errors import (
    AlreadyExistsError,
    DomainError,
    InvalidReferenceError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)
from app.web.security import CsrfRejectedError

PROBLEM_JSON = "application/problem+json"
TYPE_BASE = "https://neoine-sales.example/problems/"

# 구체적인 예외가 먼저 와야 한다(DomainError는 마지막 기본값).
_DOMAIN_MAPPING: tuple[tuple[type[DomainError], int, str], ...] = (
    (AuthenticationError, 401, "unauthenticated"),
    (AccessDeniedError, 403, "forbidden"),
    (NotFoundError, 404, "not-found"),
    (AlreadyExistsError, 409, "already-exists"),
    (InvalidReferenceError, 422, "invalid-reference"),
    (InvalidValueError, 422, "invalid-value"),
    (InvalidStateError, 409, "invalid-state"),
    (DomainError, 400, "domain-error"),
)
_TITLES = {
    "not-found": "Not Found",
    "already-exists": "Already Exists",
    "invalid-reference": "Invalid Reference",
    "invalid-value": "Invalid Value",
    "invalid-state": "Invalid State",
    "domain-error": "Domain Error",
    "request-validation": "Request Validation Failed",
    "not-ready": "Service Not Ready",
    "unauthenticated": "Unauthenticated",
    "forbidden": "Forbidden",
    "csrf": "CSRF Check Failed",
    "http-error": "HTTP Error",
}


def problem(
    request: Request,
    status: int,
    kind: str,
    detail: str,
    errors: list[dict[str, object]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"{TYPE_BASE}{kind}",
        "title": _TITLES.get(kind, kind),
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
    for error_type, status, kind in _DOMAIN_MAPPING:
        if isinstance(exc, error_type):
            return problem(request, status, kind, str(exc))
    raise exc  # 등록한 핸들러가 DomainError 하위만 받으므로 도달하지 않는다


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - 핸들러 등록 대상 보장
    errors: list[dict[str, object]] = jsonable_encoder(
        exc.errors(), exclude={"input", "ctx", "url"}
    )
    return problem(request, 422, "request-validation", "요청 형식이 올바르지 않습니다", errors)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - 핸들러 등록 대상 보장
    response = problem(request, exc.status_code, "http-error", str(exc.detail))
    for name, value in (exc.headers or {}).items():
        response.headers[name] = value
    return response


async def _csrf_error(request: Request, _: Exception) -> JSONResponse:
    return problem(request, 403, "csrf", "요청 헤더(X-Requested-With)가 필요합니다")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(CsrfRejectedError, _csrf_error)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
