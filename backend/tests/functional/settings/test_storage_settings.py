"""Feature: admin은 Admin > 외부연동에서 파일 저장 위치를 조회하고 변경하며 쓰기를 확인한다."""

from typing import TYPE_CHECKING

import pytest

from app.web.permissions import ADMIN_DENIED
from tests.functional.steps.auth import ADMIN_NAME, given_logged_in_as, storage_path_of
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.platform import then_problem_kind_is
from tests.functional.steps.settings import (
    current_user_id,
    given_dev_login_admin,
    then_updated_at_is_just_now,
    then_updated_by_is_user_ref,
)
from tests.functional.steps.storage import (
    NOT_ABSOLUTE,
    NOT_WRITABLE,
    SETTINGS_STORAGE,
    SETTINGS_STORAGE_TEST,
    STORAGE_KEYS,
    given_a_file_in_the_directory,
    given_storage_blocked_by_a_file,
    then_directory_exists,
    then_directory_is_empty,
    then_file_content_is,
    then_storage_problem_is,
    when_read_storage_settings,
    when_test_storage_settings,
    when_update_storage_settings,
    when_update_storage_settings_without_csrf_header,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api
    from tests.functional.steps.auth import RoleName

pytestmark = pytest.mark.integration


async def test_admin_reads_the_location_saved_during_the_first_setup(api: Api) -> None:
    """Scenario: admin이 조회하면 최초 설정에서 저장한 경로가 나오고 저장자는 비어 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_read_storage_settings(api)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == STORAGE_KEYS
    assert body["path"] == storage_path_of(api)
    assert body["updated_by"] is None
    then_updated_at_is_just_now(body)


async def test_admin_changes_the_location_and_the_saver_and_time_are_recorded(api: Api) -> None:
    """Scenario: admin이 위치를 바꾸면 새 경로·저장한 admin·서버 시각이 기록되고 다시 조회된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    api.clock.advance(120)
    new_path = f"{storage_path_of(api)}-moved"
    # When
    response = await when_update_storage_settings(api, new_path)
    # Then
    then_status_is(response, 200)
    body = response.json()
    assert set(body) == STORAGE_KEYS
    assert body["path"] == new_path
    then_updated_by_is_user_ref(body, user_id=await current_user_id(api), name=ADMIN_NAME)
    then_updated_at_is_just_now(body)
    assert (await when_read_storage_settings(api)).json() == body


async def test_changing_the_location_creates_the_new_directory_without_leftovers(api: Api) -> None:
    """Scenario: 새 위치 디렉터리가 없으면 만들고, 쓰기 확인용 파일은 남기지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    new_path = f"{storage_path_of(api)}-moved/deeper"
    # When
    response = await when_update_storage_settings(api, new_path)
    # Then
    then_status_is(response, 200)
    then_directory_exists(new_path)
    then_directory_is_empty(new_path)


async def test_changing_the_location_does_not_move_existing_files(api: Api) -> None:
    """Scenario: 위치를 바꿔도 기존 위치의 파일은 옮겨지지 않고 새 위치로 복사되지도 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    old_path = storage_path_of(api)
    marker = given_a_file_in_the_directory(old_path, "marker.bin", b"payload")
    new_path = f"{old_path}-moved"
    # When
    response = await when_update_storage_settings(api, new_path)
    # Then
    then_status_is(response, 200)
    then_file_content_is(marker, b"payload")
    then_directory_is_empty(new_path)


async def test_an_unwritable_location_is_rejected_and_the_old_one_is_kept(api: Api) -> None:
    """Scenario: 쓸 수 없는 위치는 고정 문구의 422이고 저장된 위치는 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    blocked = given_storage_blocked_by_a_file(api)
    # When
    response = await when_update_storage_settings(api, blocked)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_WRITABLE)
    assert (await when_read_storage_settings(api)).json()["path"] == storage_path_of(api)


@pytest.mark.parametrize("raw", ["", "relative", "/a/../b"])
async def test_a_malformed_location_is_rejected_and_the_old_one_is_kept(api: Api, raw: str) -> None:
    """Scenario: 절대 경로가 아닌 값은 422이고 저장된 위치는 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_storage_settings(api, raw)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_ABSOLUTE)
    assert (await when_read_storage_settings(api)).json()["path"] == storage_path_of(api)


async def test_the_write_test_saves_nothing(api: Api) -> None:
    """Scenario: 쓰기 확인은 204이고 저장된 위치를 바꾸지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    candidate = f"{storage_path_of(api)}-candidate"
    # When
    response = await when_test_storage_settings(api, candidate)
    # Then
    then_status_is(response, 204)
    assert (await when_read_storage_settings(api)).json()["path"] == storage_path_of(api)


async def test_the_write_test_reports_an_unwritable_location(api: Api) -> None:
    """Scenario: 쓸 수 없는 위치의 쓰기 확인은 고정 문구의 422이다."""
    # Given
    await given_logged_in_as(api, role="admin")
    blocked = given_storage_blocked_by_a_file(api)
    # When
    response = await when_test_storage_settings(api, blocked)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_WRITABLE)


async def test_reading_before_any_location_is_saved_is_404(api: Api) -> None:
    """Scenario: 저장된 위치가 없으면(옛 DB에 admin만 있는 경우) 조회는 404이다."""
    # Given
    await given_dev_login_admin(api)
    # When
    response = await when_read_storage_settings(api)
    # Then
    then_problem_kind_is(response, status=404, kinds=("not-found",))


async def test_admin_registers_the_first_location_when_none_exists(api: Api) -> None:
    """Scenario: 저장된 위치가 없는 DB에서도 admin이 위치를 처음 등록할 수 있다."""
    # Given
    await given_dev_login_admin(api)
    # When
    response = await when_update_storage_settings(api)
    # Then
    then_status_is(response, 200)
    assert (await when_read_storage_settings(api)).json()["path"] == storage_path_of(api)


@pytest.mark.parametrize("role", ["sales", "user"])
@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", SETTINGS_STORAGE),
        ("PUT", SETTINGS_STORAGE),
        ("POST", SETTINGS_STORAGE_TEST),
    ],
)
async def test_only_admin_can_use_the_storage_settings(
    api: Api, method: str, url: str, role: RoleName
) -> None:
    """Scenario: sales·user는 저장 위치 조회·변경·쓰기 확인이 403(관리자 권한 필요)이다."""
    # Given
    await given_logged_in_as(api, role=role)
    # When
    response = await api.request(method, url, json=None if method == "GET" else {"path": "/x"})
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == ADMIN_DENIED


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", SETTINGS_STORAGE),
        ("PUT", SETTINGS_STORAGE),
        ("POST", SETTINGS_STORAGE_TEST),
    ],
)
async def test_anonymous_callers_cannot_use_the_storage_settings(
    api: Api, method: str, url: str
) -> None:
    """Scenario: 로그인하지 않으면 저장 위치 API는 401이다."""
    # Given
    # (로그인하지 않은 상태)
    # When
    response = await api.request(method, url, json=None if method == "GET" else {"path": "/x"})
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


async def test_changing_the_location_needs_the_csrf_header(api: Api) -> None:
    """Scenario: CSRF 헤더 없는 변경 요청은 403이고 저장 위치는 그대로다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_update_storage_settings_without_csrf_header(api)
    # Then
    then_problem_is(response, status=403, type_suffix="csrf")
    assert (await when_read_storage_settings(api)).json()["path"] == storage_path_of(api)
