"""Feature: 최초 설정 2단계에서 파일 저장 위치를 등록·확인하고, 그 전에는 관리자를 못 만든다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import (
    given_ad_account,
    given_directory_configured,
    storage_path_of,
)
from tests.functional.steps.common import (
    then_problem_is,
    then_response_does_not_mention,
    then_status_is,
)
from tests.functional.steps.login import (
    directory_call_count,
    then_auth_flags_are,
    then_directory_was_not_asked_again,
)
from tests.functional.steps.login_db import sql_rows
from tests.functional.steps.session import then_caller_is_anonymous
from tests.functional.steps.setup import (
    given_directory_step_done,
    then_directory_must_be_saved_first,
    then_user_is_not_registered,
    when_set_up_admin,
)
from tests.functional.steps.storage import (
    NOT_ABSOLUTE,
    NOT_WRITABLE,
    PATH_TOO_LONG,
    given_storage_blocked_by_a_file,
    then_directory_does_not_exist,
    then_directory_exists,
    then_directory_is_empty,
    then_no_storage_is_saved,
    then_storage_must_be_set_first,
    then_storage_problem_is,
    then_storage_response_has,
    then_stored_path_has_no_saver,
    then_stored_path_is,
    when_save_storage,
    when_save_storage_body,
    when_test_storage_write,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_saving_the_storage_location_moves_setup_on_to_the_admin_step(api: Api) -> None:
    """Scenario: 2단계로 저장 위치를 저장하면 다음에는 최초 admin 지정만 남는다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage(api)
    # Then
    then_status_is(response, 200)
    then_storage_response_has(response, path=storage_path_of(api), saved_by_nobody=True)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=False, needs_admin=True)
    await then_stored_path_is(api, storage_path_of(api))
    await then_stored_path_has_no_saver(api)


async def test_storage_step_creates_the_missing_directory_and_leaves_no_file(api: Api) -> None:
    """Scenario: 쓰기 확인이 없는 디렉터리를 (상위 포함) 만들고 확인용 파일을 남기지 않는다."""
    # Given
    await given_directory_step_done(api)
    deep = f"{storage_path_of(api)}/level1/level2"
    then_directory_does_not_exist(deep)
    # When
    response = await when_save_storage(api, deep)
    # Then
    then_status_is(response, 200)
    then_directory_exists(deep)
    then_directory_is_empty(deep)


async def test_storage_step_stores_the_normalized_path(api: Api) -> None:
    """Scenario: 앞뒤 공백·중복 슬래시·끝 슬래시는 정리된 값으로 저장된다."""
    # Given
    await given_directory_step_done(api)
    messy = f"  {storage_path_of(api)}//nested///files/  "
    # When
    response = await when_save_storage(api, messy)
    # Then
    then_status_is(response, 200)
    expected = f"{storage_path_of(api)}/nested/files"
    then_storage_response_has(response, path=expected, saved_by_nobody=True)
    await then_stored_path_is(api, expected)


async def test_storage_step_can_be_overwritten_before_the_first_admin(api: Api) -> None:
    """Scenario: 최초 admin이 생기기 전에는 저장 위치를 다시 저장해 덮어쓸 수 있다."""
    # Given
    await given_directory_step_done(api)
    await when_save_storage(api, f"{storage_path_of(api)}/first")
    second = f"{storage_path_of(api)}/second"
    # When
    response = await when_save_storage(api, second)
    # Then
    then_status_is(response, 200)
    await then_stored_path_is(api, second)


async def test_storage_step_requires_no_session(api: Api) -> None:
    """Scenario: 저장 위치 저장은 로그인 없이 할 수 있다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage(api)
    # Then
    then_status_is(response, 200)
    await then_caller_is_anonymous(api)


@pytest.mark.parametrize("raw", ["", "   ", "relative/path", "./files", "/a/../b", "/.."])
async def test_storage_step_rejects_a_path_that_is_not_absolute(api: Api, raw: str) -> None:
    """Scenario: 빈 값·상대 경로·'..' 경로는 422로 거절되고 아무것도 저장되지 않는다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage(api, raw)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_ABSOLUTE)
    await then_no_storage_is_saved(api)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=True, needs_admin=False)


async def test_storage_step_rejects_a_path_over_1024_characters(api: Api) -> None:
    """Scenario: 1024자를 넘는 경로는 길이 안내 문구와 함께 422로 거절된다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage(api, "/" + "a" * 1024)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=PATH_TOO_LONG)
    await then_no_storage_is_saved(api)


async def test_storage_step_rejects_a_path_with_a_nul_character(api: Api) -> None:
    """Scenario: NUL 문자가 든 경로는 422로 거절되고 저장되지 않는다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage(api, "/data/\u0000files")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_no_storage_is_saved(api)


async def test_storage_step_rejects_an_unwritable_path_without_leaking_the_cause(api: Api) -> None:
    """Scenario: 디렉터리를 만들 수 없는 경로는 고정 안내 문구의 422이고 저장되지 않는다."""
    # Given
    await given_directory_step_done(api)
    blocked = given_storage_blocked_by_a_file(api)
    # When
    response = await when_save_storage(api, blocked)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_WRITABLE)
    then_response_does_not_mention(response, "Errno", "NotADirectory", "Permission", blocked)
    await then_no_storage_is_saved(api)


async def test_failed_overwrite_keeps_the_previous_storage_location(api: Api) -> None:
    """Scenario: 덮어쓰기가 쓰기 확인에서 실패하면 이전에 저장한 위치가 그대로 남는다."""
    # Given
    await given_directory_step_done(api)
    await when_save_storage(api)
    blocked = given_storage_blocked_by_a_file(api)
    # When
    response = await when_save_storage(api, blocked)
    # Then
    then_status_is(response, 422)
    await then_stored_path_is(api, storage_path_of(api))


@pytest.mark.parametrize(
    "body",
    [{}, {"path": "/data", "extra": 1}, {"path": 7}, {"path": None}],
    ids=["missing", "unknown-field", "not-a-string", "null"],
)
async def test_storage_step_rejects_a_malformed_request_body(
    api: Api, body: dict[str, object]
) -> None:
    """Scenario: path가 없거나 문자열이 아니거나 모르는 필드가 있는 본문은 422이다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_save_storage_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_no_storage_is_saved(api)


async def test_storage_step_before_the_directory_step_is_409(api: Api) -> None:
    """Scenario: AD 연결을 저장하기 전에는 저장 위치를 저장할 수 없다(409)."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_save_storage(api)
    # Then
    then_directory_must_be_saved_first(response)
    await then_no_storage_is_saved(api)


async def test_admin_cannot_be_registered_before_the_storage_step(api: Api) -> None:
    """Scenario: 저장 위치 없이 최초 admin을 지정하면 409이고 AD를 호출하지 않으며 사용자가 없다."""
    # Given
    given_ad_account(api, login_id="kim")
    await given_directory_configured(api)
    calls_before = directory_call_count(api)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_storage_must_be_set_first(response)
    then_directory_was_not_asked_again(api, calls_before=calls_before)
    await then_user_is_not_registered(api, login_id="kim")
    await then_auth_flags_are(api, needs_directory=False, needs_storage=True, needs_admin=False)


async def test_storage_first_rejection_is_not_counted_as_a_login_failure(api: Api) -> None:
    """Scenario: 저장 위치가 없어 거절된 admin 지정 시도는 로그인 실패 횟수에 남지 않는다."""
    # Given
    given_ad_account(api, login_id="kim")
    await given_directory_configured(api)
    # When
    response = await when_set_up_admin(api)
    # Then
    then_status_is(response, 409)
    assert await sql_rows(api, "select count(*) from login_failures") == [(0,)]


async def test_storage_write_test_saves_nothing(api: Api) -> None:
    """Scenario: 쓰기 확인은 204이고 저장하지 않으므로 저장 위치 단계는 계속 열려 있다."""
    # Given
    await given_directory_step_done(api)
    # When
    response = await when_test_storage_write(api)
    # Then
    then_status_is(response, 204)
    await then_no_storage_is_saved(api)
    await then_auth_flags_are(api, needs_directory=False, needs_storage=True, needs_admin=False)
    then_directory_is_empty(storage_path_of(api))


async def test_storage_write_test_does_not_need_the_directory_step(api: Api) -> None:
    """Scenario: 쓰기 확인은 AD 설정 여부와 상관없이 할 수 있다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_test_storage_write(api)
    # Then
    then_status_is(response, 204)
    await then_no_storage_is_saved(api)


@pytest.mark.parametrize(
    ("raw", "detail"),
    [("relative/path", NOT_ABSOLUTE), ("/a/../b", NOT_ABSOLUTE), ("/" + "a" * 1024, PATH_TOO_LONG)],
)
async def test_storage_write_test_rejects_a_malformed_path(api: Api, raw: str, detail: str) -> None:
    """Scenario: 쓰기 확인도 저장과 같은 형식 규칙으로 422를 돌려준다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    # When
    response = await when_test_storage_write(api, raw)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=detail)


async def test_storage_write_test_rejects_an_unwritable_path(api: Api) -> None:
    """Scenario: 쓸 수 없는 위치는 쓰기 확인에서 고정 안내 문구의 422이다."""
    # Given
    # (아무것도 설정되지 않은 새 시스템)
    blocked = given_storage_blocked_by_a_file(api)
    # When
    response = await when_test_storage_write(api, blocked)
    # Then
    then_storage_problem_is(response, status=422, type_suffix="invalid-value", detail=NOT_WRITABLE)
