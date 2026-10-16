"""첨부 라우터 단위 테스트의 공용 도우미: FakeUseCases 위의 앱, 로그인한 클라이언트, multipart 본문.

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인한다. 실제 DB·디렉터리까지 통과하는 시나리오는
functional(attachments/*)이 맡는다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Final

from httpx import ASGITransport, AsyncClient

from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories import make_deal
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import Response

UNUSED_DATABASE_URL: Final = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE: Final = "neoine_session"
DEAL_CODE: Final = "20261016-A001"
UPLOAD_URL: Final = f"/api/v1/deals/{DEAL_CODE}/attachments"
ROOT_PATH: Final = "/data/neoine-sales/files"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
DEFAULT_FILE: Final = ("a.pdf", b"hello", "application/pdf")
UPLOAD_KEYS: Final = {"outcome", "attachment"}
ATTACHMENT_KEYS: Final = {
    "id",
    "deal_code",
    "file_name",
    "description",
    "size",
    "mime",
    "uploaded_by",
    "uploaded_at",
}


async def ready_use_cases(*, storage: bool = True) -> FakeUseCases:
    """Deal 하나(20261016-A001)와 저장 위치가 있는 FakeUseCases."""
    use_cases = FakeUseCases()
    deal = make_deal(code=DEAL_CODE)
    use_cases.uow.deals._items[deal.id] = (
        deal  # 등록 유스케이스(카탈로그·연락처 시드)를 거치지 않는다
    )
    if storage:
        await use_cases.seed_storage(ROOT_PATH)
    return use_cases


@asynccontextmanager
async def client_for(
    use_cases: FakeUseCases, *, login: str | None = "kim", role: Role = Role.SALES
) -> AsyncIterator[AsyncClient]:
    """login이 None이면 익명, 아니면 그 아이디·역할로 로그인한 클라이언트."""
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if login is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal(login, role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


def form(
    file: tuple[str, bytes, str] | tuple[str, bytes] | None = (
        "a.pdf",
        b"hello",
        "application/pdf",
    ),
    **fields: str,
) -> dict[str, Any]:
    """multipart 본문(files=). file이 None이면 파일 파트가 없고, 나머지 필드는 문자 파트다."""
    parts: dict[str, Any] = {name: (None, value) for name, value in fields.items()}
    if file is not None:
        parts["file"] = file
    return parts


async def upload(
    http: AsyncClient,
    file: tuple[str, bytes, str] | None = DEFAULT_FILE,
    **fields: str,
) -> Response:
    """기본 파일(a.pdf)을 올린다. file=None이면 파일 파트 없이, fields는 문자 파트."""
    return await http.post(UPLOAD_URL, files=form(file, **fields))


def problem(response: Response, status: int, kind: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body: dict[str, Any] = response.json()
    assert str(body["type"]).endswith(kind), body
    return body
