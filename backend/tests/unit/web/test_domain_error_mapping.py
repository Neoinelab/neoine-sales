"""도메인 오류가 HTTP Problem으로 매핑되는 규칙(오류 핸들러 단위, PL-017).

유스케이스가 도메인 오류를 던지는 상황은 실제 흐름으로 만들 수 없는 종류(분류되지 않은
DomainError 등)라서 FakeUseCases에 실패하는 유스케이스를 주입해 핸들러만 검증한다.
"""

import pytest

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
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.platform_http import KIM, role_clients, then_problem_is

# (오류, 상태, kind, title) - PL-R11 순서와 2.8의 제목
CASES = [
    (AuthenticationError("세션이 만료되었습니다"), 401, "unauthenticated", "Unauthenticated"),
    (
        TooManyAttemptsError("잠시 후 다시 시도하세요"),
        429,
        "too-many-attempts",
        "Too Many Attempts",
    ),
    (AccessDeniedError("권한이 없습니다"), 403, "forbidden", "Forbidden"),
    (NotFoundError("항목", "x"), 404, "not-found", "Not Found"),
    (AttachmentNameTakenError("a.txt"), 409, "file-exists", "File Exists"),
    (AlreadyExistsError("코드", "x"), 409, "already-exists", "Already Exists"),
    (InvalidReferenceError("고객", "x"), 422, "invalid-reference", "Invalid Reference"),
    (InvalidValueError("값이 올바르지 않습니다"), 422, "invalid-value", "Invalid Value"),
    (InvalidStateError("삭제된 항목은 수정할 수 없습니다"), 409, "invalid-state", "Invalid State"),
    (DomainError("알 수 없는 도메인 오류"), 400, "domain-error", "Domain Error"),
]


@pytest.mark.parametrize(
    ("error", "status", "kind", "title"), CASES, ids=[kind for _, _, kind, _ in CASES]
)
async def test_domain_errors_become_problems_by_their_kind(
    error: DomainError, status: int, kind: str, title: str
) -> None:
    """도메인 오류는 종류별 상태·kind·문구로 바뀐다.

    테스트 코드: PL-017
    """
    # given: 연락처 회사 목록 유스케이스가 그 도메인 오류를 던지는 앱
    use_cases = FakeUseCases()

    class Failing:
        async def execute(self, *_: object, **__: object) -> None:
            raise error

    use_cases.list_contact_companies = Failing  # type: ignore[method-assign, assignment, unused-ignore]
    async with role_clients(use_cases) as c:
        # when: 그 경로를 부른다
        response = await c[KIM].get("/api/v1/contacts/companies", params={"kind": "customer"})
    # then: PL-R11의 상태와 kind, 2.8의 title이고 detail은 오류 메시지 그대로다
    body = then_problem_is(response, status, kind)
    assert body["title"] == title
    assert body["detail"] == str(error)
