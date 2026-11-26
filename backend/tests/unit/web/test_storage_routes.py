"""저장 위치 라우터: FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다.

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다.
실제 디렉터리 쓰기 확인은 `tests/unit/infra/`의
파일 저장소 단위 테스트가 본다.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories import NOW
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from httpx import Response

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다
SESSION_COOKIE = "neoine_session"
SETUP_STORAGE = "/api/v1/auth/setup/storage"
SETUP_STORAGE_TEST = "/api/v1/auth/setup/storage/test"
SETTINGS_STORAGE = "/api/v1/settings/storage"
SETTINGS_STORAGE_TEST = "/api/v1/settings/storage/test"
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."
NOT_ABSOLUTE = "절대 경로를 입력하세요."
ADMIN_DENIED = "관리자 권한이 필요합니다"


@asynccontextmanager
async def _client(
    use_cases: FakeUseCases, *, role: Role | None = None
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_settings(UNUSED_DATABASE_URL), use_cases=use_cases)
    cookies = {}
    if role is not None:
        cookies[SESSION_COOKIE] = await use_cases.login_as(make_principal("root", role))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=CSRF_HEADER,
        cookies=cookies,
    ) as http:
        yield http


def _problem(response: Response, status: int, kind: str) -> dict[str, object]:
    assert response.status_code == status, response.text
    body = response.json()
    assert str(body["type"]).endswith(kind), body
    return dict(body)


# ---- 최초 설정 2단계(공개) ----


async def test_setup_storage_saves_and_returns_the_settings_without_a_saver() -> None:
    """최초 설정 저장 위치 등록은 정규화한 경로와 등록자 없음(updated_by null)을 돌려준다."""
    # given: AD 서버가 등록되었다
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    await use_cases.seed_auth_mode(AuthMode.AD)
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": " /data//neoine/files/ "})

    assert response.status_code == 200, response.text
    # when: 공백·중복 슬래시가 섞인 경로로 등록한다
    body = response.json()
    # then: 200, 정규화한 경로, updated_by null
    assert set(body) == {"path", "updated_at", "updated_by"}
    assert (body["path"], body["updated_by"]) == ("/data/neoine/files", None)
    assert use_cases.file_storage.dir_exists("/data/neoine/files")


async def test_setup_storage_test_returns_204_with_no_body_and_saves_nothing() -> None:
    """쓰기 테스트는 본문 없는 204이고 저장 위치 단계는 열린 채다."""
    # given: 저장 위치가 아직 없다
    use_cases = FakeUseCases()
    # when: 쓰기 테스트를 한다
    async with _client(use_cases) as http:
        response = await http.post(SETUP_STORAGE_TEST, json={"path": "/data/files"})
        config = await http.get("/api/v1/auth/config")

    # then: 204, 본문 없음, 진행 상태의 저장 단계 그대로
    assert (response.status_code, response.content) == (204, b"")
    assert config.json()["needs_storage_setup"] is True


# ---- Admin > 외부연동 ----


async def test_admin_reads_the_saved_settings() -> None:
    """admin이 저장 위치를 조회하면 경로가 나오고 최초 설정 행의 저장자는 비어 있다.

    테스트 코드: IN-043
    """
    # given: 최초 설정으로 저장된 위치 /data/saved
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/saved")
    # when: admin이 GET /settings/storage를 부른다
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.get(SETTINGS_STORAGE)

    # then: 200이고 path가 /data/saved, updated_by가 null이다
    assert response.status_code == 200, response.text
    assert response.json()["path"] == "/data/saved"
    assert response.json()["updated_by"] is None


async def test_reading_without_saved_settings_is_404_not_found() -> None:
    """저장 위치가 없으면 조회는 404 not-found다.

    테스트 코드: IN-044
    """
    # given: 저장 위치 행이 없다
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.get(SETTINGS_STORAGE)

    # when·then: admin이 저장 위치를 조회한다 → 404 not-found다
    _problem(response, 404, "not-found")


async def test_admin_update_records_the_admin_as_the_saver() -> None:
    """admin이 저장 위치를 바꾸면 새 경로와 저장자가 응답에 담긴다.

    테스트 코드: IN-045
    """
    # given: 저장 위치가 없다
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.put(SETTINGS_STORAGE, json={"path": "/data/new"})
        me = (await http.get("/api/v1/auth/me")).json()

    assert response.status_code == 200, response.text
    # when: admin이 /data/new로 저장한다
    body = response.json()
    # then: 200이고 path와 저장자(UserRef 5필드)가 응답에 있다
    assert body["path"] == "/data/new"
    assert body["updated_by"]["id"] == me["user_id"]
    assert set(body["updated_by"]) == {"id", "name", "resigned", "label", "role"}


async def test_admin_update_with_an_unwritable_path_is_422_and_keeps_the_old_path() -> None:
    """쓸 수 없는 위치는 고정 문구 422이고 기존 위치는 그대로다.

    테스트 코드: IN-050
    """
    # given: 저장 위치 /data/old와 쓸 수 없는 경로
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/old")
    use_cases.file_storage.block("/blocked")
    # when: admin이 쓸 수 없는 경로로 저장한다
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.put(SETTINGS_STORAGE, json={"path": "/blocked/files"})
        current = await http.get(SETTINGS_STORAGE)

    # then: 422 invalid-value 고정 문구이고 조회하면 /data/old다
    assert _problem(response, 422, "invalid-value")["detail"] == NOT_WRITABLE
    assert current.json()["path"] == "/data/old"


async def test_admin_write_test_is_204_and_saves_nothing() -> None:
    """쓰기 테스트는 204(본문 없음)이고 저장 위치를 바꾸지 않는다.

    테스트 코드: IN-054
    """
    # given: 저장 위치 /data/old
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/old")
    # when: admin이 /data/candidate로 쓰기 테스트한다
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.post(SETTINGS_STORAGE_TEST, json={"path": "/data/candidate"})
        current = await http.get(SETTINGS_STORAGE)

    # then: 204이고 본문이 비어 있으며 조회하면 /data/old다
    assert (response.status_code, response.content) == (204, b"")
    assert current.json()["path"] == "/data/old"


async def test_sales_cannot_use_the_storage_settings_even_with_a_bad_body() -> None:
    """sales는 저장 위치 세 경로를 본문 검사 전에 403으로 거절당한다.

    테스트 코드: IN-040
    """
    # given: sales로 로그인했다
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.SALES) as http:
        # when: 저장 위치 조회·저장·쓰기 테스트를 잘못된 본문으로 부른다
        responses = [
            await http.get(SETTINGS_STORAGE),
            await http.put(SETTINGS_STORAGE, json={"garbage": 1}),
            await http.post(SETTINGS_STORAGE_TEST, json={"garbage": 1}),
        ]

    # then: 세 경로 모두 본문 검사 전에 403 forbidden이다
    for response in responses:
        assert _problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED


async def test_anonymous_callers_get_401_on_the_storage_settings() -> None:
    """로그인하지 않으면 저장 위치 세 경로가 401이다.

    테스트 코드: IN-040
    """
    # given: 로그인하지 않은 호출자다
    async with _client(FakeUseCases()) as http:
        # when: 저장 위치 조회·저장·쓰기 테스트를 부른다
        responses = [
            await http.get(SETTINGS_STORAGE),
            await http.put(SETTINGS_STORAGE, json={"path": "/x"}),
            await http.post(SETTINGS_STORAGE_TEST, json={"path": "/x"}),
        ]

    # then: 세 경로 모두 401 unauthenticated다
    for response in responses:
        _problem(response, 401, "unauthenticated")


async def test_admin_update_records_the_server_clock_with_its_offset(
    local_tz: Callable[[str], None],
) -> None:
    """저장 위치를 바꾸면 새 경로·저장자·서버 시계의 오프셋 시각이 기록되고 다시 조회된다.

    테스트 코드: IN-045
    """
    # given: 서울 시간대 서버, 저장 위치 /data/a
    local_tz("Asia/Seoul")
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/a")
    async with _client(use_cases, role=Role.ADMIN) as http:
        # when: BOSS가 /data/b로 바꾼다
        saved = await http.put(SETTINGS_STORAGE, json={"path": "/data/b"})
        read = await http.get(SETTINGS_STORAGE)
        me = (await http.get("/api/v1/auth/me")).json()

    # then: 응답과 이후 조회가 같고 경로·저장자·서버 시각(+09:00)이 맞다
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["path"], body["updated_by"]["id"]) == ("/data/b", me["user_id"])
    assert body["updated_at"].endswith("+09:00")
    assert NOW <= datetime.fromisoformat(body["updated_at"]) <= use_cases.clock.now()
    assert read.json() == body


@pytest.mark.parametrize(
    "body",
    [{}, {"path": 1}, {"path": None}, {"path": "/a", "x": 1}],
    ids=["missing", "not-a-string", "null", "unknown-field"],
)
async def test_a_malformed_storage_request_is_422_request_validation(
    body: dict[str, object],
) -> None:
    """path가 없거나 문자열이 아니거나 모르는 필드가 있으면 422 request-validation이다.

    테스트 코드: IN-056
    """
    # given: 저장 위치 /data/a
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/a")
    async with _client(use_cases, role=Role.ADMIN) as http:
        # when: BOSS가 모양이 틀린 본문으로 저장한다
        response = await http.put(SETTINGS_STORAGE, json=body)
        current = await http.get(SETTINGS_STORAGE)

    # then: 422 request-validation이고 저장 위치는 그대로다
    _problem(response, 422, "request-validation")
    assert current.json()["path"] == "/data/a"


@pytest.mark.parametrize(
    ("path", "detail"),
    [("", NOT_ABSOLUTE), ("/" + "a" * 2000, "저장 경로는 1024자 이내로 입력하세요.")],
)
async def test_an_empty_or_overlong_storage_path_is_422_with_the_domain_message(
    path: str, detail: str
) -> None:
    """빈 값과 2000자 경로는 422 invalid-value와 도메인 문구다.

    테스트 코드: IN-056
    """
    # given: 저장 위치 /data/a
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/a")
    async with _client(use_cases, role=Role.ADMIN) as http:
        # when: BOSS가 빈 값 또는 2000자 경로로 저장한다
        response = await http.put(SETTINGS_STORAGE, json={"path": path})

    # then: 422 invalid-value와 도메인 문구
    assert _problem(response, 422, "invalid-value")["detail"] == detail
