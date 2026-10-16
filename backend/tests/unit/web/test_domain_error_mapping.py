"""도메인 오류가 HTTP Problem으로 매핑되는 규칙(오류 핸들러 단위).

유스케이스가 도메인 오류를 던지는 상황은 실제 DB 흐름으로 만들 수 없는 종류(분류되지 않은
DomainError 등)라서 FakeUseCases에 실패하는 유스케이스를 주입해 핸들러만 검증한다.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.domain.common.errors import DomainError, InvalidStateError
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"


@pytest.mark.parametrize(
    ("error", "status", "type_suffix"),
    [
        (InvalidStateError("삭제된 항목은 수정할 수 없습니다"), 409, "invalid-state"),
        (DomainError("알 수 없는 도메인 오류"), 400, "domain-error"),
    ],
)
async def test_other_domain_errors_are_mapped(
    error: DomainError, status: int, type_suffix: str
) -> None:
    use_cases = FakeUseCases()

    class Failing:
        async def execute(self, *_: object, **__: object) -> None:
            raise error

    use_cases.list_contact_companies = Failing  # type: ignore[method-assign, assignment, unused-ignore]
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    token = await use_cases.login_as(make_principal("sales-user", Role.SALES))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: token},
    ) as http:
        response = await http.get("/api/v1/contacts/companies", params={"kind": "customer"})

    assert response.status_code == status
    assert response.json()["type"].endswith(type_suffix)
    assert response.json()["detail"] == str(error)
