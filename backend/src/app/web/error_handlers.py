"""오류를 RFC 9457 problem+json으로 바꾼다. 내부 예외 메시지는 도메인 오류만 노출한다."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.directory.errors import DirectoryVerificationError
from app.application.ports.directory import DirectoryUnavailableError
from app.application.ports.report_query_runner import ReportQueryTimeoutError
from app.application.storage.errors import StorageUnavailableError
from app.domain.attachment.errors import AttachmentNameTakenError
from app.domain.auth.errors import AccessDeniedError, AuthenticationError, TooManyAttemptsError
from app.domain.common.errors import (
    AlreadyExistsError,
    DomainError,
    InvalidReferenceError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)
from app.domain.report.errors import ReportDefinitionError
from app.domain.report.vocabulary import STATEMENT_TIMEOUT_SECONDS
from app.web.security import CsrfRejectedError

PROBLEM_JSON = "application/problem+json"
TYPE_BASE = "https://neoine-sales.example/problems/"

# 구체적인 예외가 먼저 와야 한다(DomainError는 마지막 기본값).
_DOMAIN_MAPPING: tuple[tuple[type[DomainError], int, str], ...] = (
    (AuthenticationError, 401, "unauthenticated"),
    (TooManyAttemptsError, 429, "too-many-attempts"),
    (AccessDeniedError, 403, "forbidden"),
    (NotFoundError, 404, "not-found"),
    (AttachmentNameTakenError, 409, "file-exists"),
    (AlreadyExistsError, 409, "already-exists"),
    (InvalidReferenceError, 422, "invalid-reference"),
    (InvalidValueError, 422, "invalid-value"),
    (InvalidStateError, 409, "invalid-state"),
    (DomainError, 400, "domain-error"),
)
_TITLES = {
    "not-found": "Not Found",
    "already-exists": "Already Exists",
    "file-exists": "File Exists",
    "invalid-reference": "Invalid Reference",
    "invalid-value": "Invalid Value",
    "invalid-state": "Invalid State",
    "domain-error": "Domain Error",
    "request-validation": "Request Validation Failed",
    "not-ready": "Service Not Ready",
    "unauthenticated": "Unauthenticated",
    "forbidden": "Forbidden",
    "too-many-attempts": "Too Many Attempts",
    "directory-unavailable": "Directory Unavailable",
    "directory-verification-failed": "Directory Verification Failed",
    "storage-unavailable": "Storage Unavailable",
    "invalid-report": "Invalid Report",
    "report-timeout": "Report Timeout",
    "csrf": "CSRF Check Failed",
    "http-error": "HTTP Error",
}


def problem(
    request: Request,
    status: int,
    kind: str,
    detail: str,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"{TYPE_BASE}{kind}",
        "title": _TITLES.get(kind, kind),
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


DIRECTORY_UNAVAILABLE_DETAIL = "인증 서버(AD)에 연결할 수 없습니다. 잠시 후 다시 시도하세요"


async def _directory_unavailable(request: Request, _: Exception) -> JSONResponse:
    """AD 장애 원인(주소·서버 응답)은 응답에 싣지 않고 고정 문구만 낸다."""
    return problem(request, 503, "directory-unavailable", DIRECTORY_UNAVAILABLE_DETAIL)


async def _storage_unavailable(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StorageUnavailableError)  # noqa: S101 - 핸들러 등록 대상 보장
    return problem(request, 503, "storage-unavailable", exc.message)


REPORT_TIMEOUT_DETAIL = (
    f"조회가 {STATEMENT_TIMEOUT_SECONDS}초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요"
)


async def _report_timeout(request: Request, _: Exception) -> JSONResponse:
    """DB 취소 사유는 응답에 싣지 않고 고정 문구만 낸다."""
    return problem(request, 503, "report-timeout", REPORT_TIMEOUT_DETAIL)


async def _invalid_report(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ReportDefinitionError)  # noqa: S101 - 핸들러 등록 대상 보장
    errors = [
        {"location": list(i.location), "code": i.code, "message": i.message} for i in exc.issues
    ]
    return problem(request, 422, "invalid-report", str(exc), {"errors": errors})


async def _directory_verification(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DirectoryVerificationError)  # noqa: S101 - 핸들러 등록 대상 보장
    return problem(
        request, 422, "directory-verification-failed", exc.message, extra={"stage": str(exc.stage)}
    )


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
    return problem(
        request, 422, "request-validation", "요청 형식이 올바르지 않습니다", {"errors": errors}
    )


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
    app.add_exception_handler(DirectoryVerificationError, _directory_verification)
    app.add_exception_handler(DirectoryUnavailableError, _directory_unavailable)
    app.add_exception_handler(StorageUnavailableError, _storage_unavailable)
    app.add_exception_handler(ReportQueryTimeoutError, _report_timeout)
    app.add_exception_handler(ReportDefinitionError, _invalid_report)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
