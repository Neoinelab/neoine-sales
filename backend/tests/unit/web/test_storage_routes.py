"""저장 위치 라우터(P2b AC-02·03·05): FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다.

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다. 실제 DB·디렉터리까지 통과하는
시나리오는 functional(setup/test_setup_storage.py, settings/test_storage_settings.py)이 맡는다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from httpx import ASGITransport, AsyncClient

from app.application.auth.messages import DIRECTORY_FIRST, SETUP_CLOSED
from app.domain.auth.principal import Role
from app.main import create_app
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.conftest import CSRF_HEADER, make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": " /data//neoine/files/ "})

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"path", "updated_at", "updated_by"}
    assert (body["path"], body["updated_by"]) == ("/data/neoine/files", None)
    assert use_cases.file_storage.dir_exists("/data/neoine/files")


async def test_setup_storage_before_the_directory_step_is_409() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/data/files"})

    assert _problem(response, 409, "invalid-state")["detail"] == DIRECTORY_FIRST


async def test_setup_storage_after_the_first_admin_is_409_closed() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    await use_cases.seed_user("boss", Role.ADMIN)
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/data/files"})

    assert _problem(response, 409, "invalid-state")["detail"] == SETUP_CLOSED


async def test_setup_storage_with_an_unwritable_path_is_422_with_the_fixed_message() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    use_cases.file_storage.block("/blocked")
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/blocked/files"})

    assert _problem(response, 422, "invalid-value")["detail"] == NOT_WRITABLE


async def test_setup_storage_with_a_relative_path_is_422() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "relative/files"})

    assert _problem(response, 422, "invalid-value")["detail"] == NOT_ABSOLUTE


async def test_setup_storage_rejects_an_unknown_field_as_a_request_validation_error() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    async with _client(use_cases) as http:
        response = await http.put(SETUP_STORAGE, json={"path": "/data", "mode": "0777"})

    _problem(response, 422, "request-validation")


async def test_setup_storage_test_returns_204_with_no_body_and_saves_nothing() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases) as http:
        response = await http.post(SETUP_STORAGE_TEST, json={"path": "/data/files"})
        config = await http.get("/api/v1/auth/config")

    assert (response.status_code, response.content) == (204, b"")
    assert config.json()["needs_storage_setup"] is True


async def test_auth_config_reports_the_storage_step_after_the_directory_step() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    async with _client(use_cases) as http:
        config = (await http.get("/api/v1/auth/config")).json()

    assert (
        config["needs_directory_setup"],
        config["needs_storage_setup"],
        config["needs_admin_setup"],
    ) == (False, True, False)


async def test_auth_config_moves_to_the_admin_step_once_storage_is_saved() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_directory()
    await use_cases.seed_storage()
    async with _client(use_cases) as http:
        config = (await http.get("/api/v1/auth/config")).json()

    assert (
        config["needs_directory_setup"],
        config["needs_storage_setup"],
        config["needs_admin_setup"],
    ) == (False, False, True)


# ---- Admin > 외부연동 ----


async def test_admin_reads_the_saved_settings() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/saved")
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.get(SETTINGS_STORAGE)

    assert response.status_code == 200, response.text
    assert response.json()["path"] == "/data/saved"
    assert response.json()["updated_by"] is None


async def test_reading_without_saved_settings_is_404_not_found() -> None:
    async with _client(FakeUseCases(), role=Role.ADMIN) as http:
        response = await http.get(SETTINGS_STORAGE)

    _problem(response, 404, "not-found")


async def test_admin_update_records_the_admin_as_the_saver() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.put(SETTINGS_STORAGE, json={"path": "/data/new"})
        me = (await http.get("/api/v1/auth/me")).json()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["path"] == "/data/new"
    assert body["updated_by"]["id"] == me["user_id"]
    assert set(body["updated_by"]) == {"id", "name", "resigned", "label", "role"}


async def test_admin_update_with_an_unwritable_path_is_422_and_keeps_the_old_path() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/old")
    use_cases.file_storage.block("/blocked")
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.put(SETTINGS_STORAGE, json={"path": "/blocked/files"})
        current = await http.get(SETTINGS_STORAGE)

    assert _problem(response, 422, "invalid-value")["detail"] == NOT_WRITABLE
    assert current.json()["path"] == "/data/old"


async def test_admin_write_test_is_204_and_saves_nothing() -> None:
    use_cases = FakeUseCases()
    await use_cases.seed_storage("/data/old")
    async with _client(use_cases, role=Role.ADMIN) as http:
        response = await http.post(SETTINGS_STORAGE_TEST, json={"path": "/data/candidate"})
        current = await http.get(SETTINGS_STORAGE)

    assert (response.status_code, response.content) == (204, b"")
    assert current.json()["path"] == "/data/old"


async def test_sales_cannot_use_the_storage_settings_even_with_a_bad_body() -> None:
    use_cases = FakeUseCases()
    async with _client(use_cases, role=Role.SALES) as http:
        responses = [
            await http.get(SETTINGS_STORAGE),
            await http.put(SETTINGS_STORAGE, json={"garbage": 1}),
            await http.post(SETTINGS_STORAGE_TEST, json={"garbage": 1}),
        ]

    for response in responses:
        assert _problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED


async def test_anonymous_callers_get_401_on_the_storage_settings() -> None:
    async with _client(FakeUseCases()) as http:
        responses = [
            await http.get(SETTINGS_STORAGE),
            await http.put(SETTINGS_STORAGE, json={"path": "/x"}),
            await http.post(SETTINGS_STORAGE_TEST, json={"path": "/x"}),
        ]

    for response in responses:
        _problem(response, 401, "unauthenticated")
