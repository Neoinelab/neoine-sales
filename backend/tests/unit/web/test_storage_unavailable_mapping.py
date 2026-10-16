"""StorageUnavailableError(저장 위치 사용 불가)가 503 Problem(storage-unavailable)으로 매핑된다.

도메인 오류가 아니라 application 오류라 전용 핸들러가 필요하다(P2b AC-09·13).
업로드·다운로드 API는 R2에서 생기므로 FakeUseCases에 실패하는 유스케이스를 주입해 핸들러만 검증한다.
"""

from typing import TYPE_CHECKING

import pytest
from app.application.storage.errors import (
    DOWNLOAD_UNAVAILABLE,
    UPLOAD_UNAVAILABLE,
    StorageUnavailableError,
)
from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from httpx import Response

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"


async def _call_failing_with(error: Exception) -> Response:
    use_cases = FakeUseCases()

    class Failing:
        async def execute(self, *_: object, **__: object) -> None:
            raise error

    use_cases.get_storage_settings = Failing  # type: ignore[method-assign, assignment, unused-ignore]
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    token = await use_cases.login_as(make_principal("root", Role.ADMIN))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies={SESSION_COOKIE: token},
    ) as http:
        return await http.get("/api/v1/settings/storage")


def test_the_unavailable_messages_are_the_fixed_sentences() -> None:
    assert (
        UPLOAD_UNAVAILABLE
        == "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."
    )
    assert DOWNLOAD_UNAVAILABLE == "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."


def test_the_error_carries_its_message() -> None:
    assert str(StorageUnavailableError("저장 위치 문구")) == "저장 위치 문구"


@pytest.mark.parametrize("message", [UPLOAD_UNAVAILABLE, DOWNLOAD_UNAVAILABLE])
async def test_storage_unavailable_is_a_503_problem_with_the_error_message_as_detail(
    message: str,
) -> None:
    response = await _call_failing_with(StorageUnavailableError(message))

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"].endswith("/storage-unavailable")
    assert body["title"] == "Storage Unavailable"
    assert body["status"] == 503
    assert body["detail"] == message
    assert body["instance"] == "/api/v1/settings/storage"


def test_storage_unavailable_is_not_a_domain_error() -> None:
    from app.domain.common.errors import DomainError  # noqa: PLC0415

    assert not issubclass(StorageUnavailableError, DomainError)
