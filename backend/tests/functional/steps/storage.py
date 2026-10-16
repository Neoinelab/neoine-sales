"""파일 저장 위치 feature의 step: 최초 설정 2단계(공개)와 Admin > 외부연동 저장 위치(admin 전용).

디스크 확인은 시나리오의 저장 디렉터리(`api.storage_root`, tmp_path 아래)를 직접 본다.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from tests.functional.steps.auth import SETUP_STORAGE, SETUP_STORAGE_TEST, storage_path_of
from tests.functional.steps.login import WITHOUT_CSRF_HEADER
from tests.functional.steps.login_db import sql_rows

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

SETTINGS_STORAGE = "/api/v1/settings/storage"
SETTINGS_STORAGE_TEST = "/api/v1/settings/storage/test"
STORAGE_KEYS = {"path", "updated_at", "updated_by"}
NOT_ABSOLUTE = "절대 경로를 입력하세요."
PATH_TOO_LONG = "저장 경로는 1024자 이내로 입력하세요."
NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."


def _body(api: Api, path: str | None) -> dict[str, str]:
    return {"path": storage_path_of(api) if path is None else path}


# ---- Given ----


def given_storage_blocked_by_a_file(api: Api) -> str:
    """저장 위치 경로의 상위가 일반 파일이라 디렉터리를 만들 수 없다. 그 경로를 돌려준다."""
    blocker = Path(storage_path_of(api)).parent / "blocker"
    blocker.write_bytes(b"i am a regular file")
    return f"{blocker}/files"


def given_a_file_in_the_directory(directory: str, name: str, data: bytes = b"keep") -> Path:
    """디스크의 저장 디렉터리에 파일 하나가 있다(옮기지 않는지 보려는 표식)."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / name
    marker.write_bytes(data)
    return marker


# ---- When: 최초 설정 2단계(공개) ----


async def when_save_storage(api: Api, path: str | None = None) -> Response:
    """최초 설정 2단계: 파일 저장 위치를 저장한다(path가 없으면 이 시나리오의 저장 디렉터리)."""
    return await api.put(SETUP_STORAGE, json=_body(api, path))


async def when_save_storage_body(api: Api, body: dict[str, object]) -> Response:
    """최초 설정 2단계에 임의의 본문을 그대로 보낸다(알 수 없는 필드·누락 검증용)."""
    return await api.put(SETUP_STORAGE, json=body)


async def when_test_storage_write(api: Api, path: str | None = None) -> Response:
    """최초 설정 2단계: 저장하지 않고 쓰기만 확인한다."""
    return await api.post(SETUP_STORAGE_TEST, json=_body(api, path))


async def when_save_storage_without_csrf_header(api: Api, *, test: bool = False) -> Response:
    url, method = (SETUP_STORAGE_TEST, "POST") if test else (SETUP_STORAGE, "PUT")
    return await api.request(method, url, json=_body(api, None), headers=WITHOUT_CSRF_HEADER)


# ---- When: Admin > 외부연동 ----


async def when_read_storage_settings(api: Api) -> Response:
    return await api.get(SETTINGS_STORAGE)


async def when_update_storage_settings(api: Api, path: str | None = None) -> Response:
    return await api.put(SETTINGS_STORAGE, json=_body(api, path))


async def when_test_storage_settings(api: Api, path: str | None = None) -> Response:
    return await api.post(SETTINGS_STORAGE_TEST, json=_body(api, path))


async def when_update_storage_settings_without_csrf_header(api: Api) -> Response:
    return await api.request(
        "PUT", SETTINGS_STORAGE, json=_body(api, None), headers=WITHOUT_CSRF_HEADER
    )


# ---- Then ----


def then_storage_must_be_set_first(response: Response) -> None:
    """관리자 등록 전에 저장 위치가 필요하다: 409 invalid-state와 안내 문구."""
    from app.application.auth.messages import STORAGE_FIRST  # noqa: PLC0415 - 구현 전에도 수집

    assert response.status_code == 409, response.text
    assert str(response.json()["type"]).endswith("invalid-state")
    assert response.json()["detail"] == STORAGE_FIRST


def then_storage_problem_is(
    response: Response, *, status: int, type_suffix: str, detail: str
) -> None:
    """저장 위치 단계의 Problem 응답: 상태 코드, type, 사용자에게 보이는 문구가 모두 같다."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert str(response.json()["type"]).endswith(type_suffix), response.json()
    assert response.json()["detail"] == detail


def then_storage_response_has(response: Response, *, path: str, saved_by_nobody: bool) -> None:
    """저장 위치 응답 본문의 키 집합과 경로, 저장자가 비었는지."""
    body = response.json()
    assert set(body) == STORAGE_KEYS, body
    assert body["path"] == path
    assert (body["updated_by"] is None) is saved_by_nobody
    assert body["updated_at"]


async def then_no_storage_is_saved(api: Api) -> None:
    """저장 위치가 하나도 저장되지 않았다."""
    assert await sql_rows(api, "select count(*) from storage_settings") == [(0,)]


async def then_stored_path_is(api: Api, expected: str) -> None:
    """DB에 저장된 저장 위치 경로(행은 하나)."""
    rows = await sql_rows(api, "select path from storage_settings")
    assert rows == [(expected,)]


async def then_stored_path_has_no_saver(api: Api) -> None:
    """최초 설정에서 저장한 저장 위치는 저장자(사용자 FK)가 비어 있다."""
    assert await sql_rows(api, "select updated_by_user_id from storage_settings") == [(None,)]


def then_directory_exists(path: str) -> None:
    assert Path(path).is_dir(), path


def then_directory_is_empty(path: str) -> None:
    """쓰기 확인이 흔적(임시 파일)을 남기지 않았다."""
    assert [child.name for child in Path(path).iterdir()] == []


def then_directory_does_not_exist(path: str) -> None:
    assert not Path(path).exists(), path


def then_file_content_is(path: Path, expected: bytes) -> None:
    assert path.read_bytes() == expected
