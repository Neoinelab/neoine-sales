"""Feature: 사원은 회사 AD 계정으로 로그인해 세션 쿠키를 받고, 명단이 모호해도 안전하게 거절된다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.factories_auth import BASE_DN
from tests.functional.steps.auth import given_logged_out, password_of
from tests.functional.steps.common import then_status_is
from tests.functional.steps.login import (
    given_employee,
    then_directory_was_asked_with_base_dn,
    then_last_login_is_recorded,
    then_login_failed_with_the_common_401,
    then_no_cookie_is_set,
    then_no_password_hash_is_stored,
    then_password_hash_is_stored_for,
    then_signed_in_as,
    when_log_in,
)
from tests.functional.steps.login_db import (
    given_directory_settings_changed_in_database,
    given_extra_user_row,
)
from tests.functional.steps.session import (
    session_cookie_header,
    then_me_is,
    then_session_cookie_is_http_only_lax,
)
from tests.functional.steps.setup import given_setup_completed_by

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_employee_signs_in_and_gets_an_http_only_lax_session_cookie(api: Api) -> None:
    """Scenario: 등록된 사원이 AD 비밀번호로 로그인하면 HttpOnly·Lax 세션 쿠키를 받는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api)
    # Then
    then_signed_in_as(response, subject="kim", email="kim@corp.test", name="김영업", role="sales")
    then_session_cookie_is_http_only_lax(response)
    await then_me_is(api, subject="kim")


async def test_login_never_sets_the_legacy_login_cookie(api: Api) -> None:
    """Scenario: 로그인 응답은 폐지된 neoine_login 쿠키를 내려주지 않는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api)
    # Then
    assert "neoine_login" not in "".join(response.headers.get_list("set-cookie"))


async def test_login_cookie_is_secure_when_the_deployment_requires_it(api: Api) -> None:
    """Scenario: cookie_secure 설정이 켜진 배포에서는 세션 쿠키에 Secure 속성이 붙는다."""
    # Given
    await given_employee(api)
    await api.reopen(cookie_secure=True)
    # When
    response = await when_log_in(api)
    # Then
    assert "secure" in session_cookie_header(response).lower().split("; ")


async def test_login_id_is_normalized_before_the_directory_lookup(api: Api) -> None:
    """Scenario: 앞뒤 공백과 대문자가 섞인 아이디로도 같은 사원으로 로그인된다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api, login_id=" KIM ", password=password_of("kim"))
    # Then
    then_status_is(response, 200)
    assert response.json()["subject"] == "kim"


async def test_successful_login_records_the_last_login_time(api: Api) -> None:
    """Scenario: 로그인에 성공하면 사용자 목록에 최근 로그인 시각이 남는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api)
    # Then
    then_status_is(response, 200)
    await then_last_login_is_recorded(api, login_id="kim")


async def test_admin_who_finished_setup_can_sign_in_again_after_logging_out(api: Api) -> None:
    """Scenario: 최초 설정을 마친 admin이 로그아웃한 뒤 같은 AD 비밀번호로 다시 로그인한다."""
    # Given
    await given_setup_completed_by(api, login_id="kim", display_name="김관리", email="k@c.test")
    await given_logged_out(api)
    # When
    response = await when_log_in(api)
    # Then
    then_signed_in_as(response, subject="kim", email="k@c.test", name="김관리", role="admin")


async def test_login_with_two_active_rows_for_one_login_id_is_a_plain_401(api: Api) -> None:
    """Scenario: 재직 사용자 행이 둘이면 500이 아니라 공통 401이고 세션 쿠키가 없다."""
    # Given
    await given_employee(api)
    await given_extra_user_row(api, login_id="kim", role=Role.USER)
    # When
    response = await when_log_in(api)
    # Then
    then_login_failed_with_the_common_401(response)


async def test_login_succeeds_when_one_row_is_resigned_and_one_is_active(api: Api) -> None:
    """Scenario: 퇴사 행 1개와 재직 행 1개가 있으면 재직 행(sales)으로 정상 로그인된다."""
    # Given
    await given_employee(api)
    await given_extra_user_row(api, login_id="kim", role=Role.USER, resigned=True)
    # When
    response = await when_log_in(api)
    # Then
    then_status_is(response, 200)
    assert response.json()["role"] == "sales"


async def test_login_with_a_resigned_row_and_two_active_rows_is_a_plain_401(api: Api) -> None:
    """Scenario: 퇴사 행 1개와 재직 행 2개가 DB에 있어도 로그인은 공통 401이다(PostgreSQL)."""
    # Given
    await given_employee(api)
    await given_extra_user_row(api, login_id="kim", role=Role.USER, resigned=True)
    await given_extra_user_row(api, login_id="kim", role=Role.USER)
    # When
    response = await when_log_in(api)
    # Then
    then_login_failed_with_the_common_401(response)
    then_no_cookie_is_set(response)


async def test_new_directory_settings_apply_to_the_next_login(api: Api) -> None:
    """Scenario: AD 설정이 DB에서 바뀌면 이미 떠 있는 서버도 다음 로그인부터 새 설정을 쓴다."""
    # Given
    await given_employee(api)
    await api.reopen()  # 같은 DB를 보는 다른 서버 인스턴스
    await when_log_in(api)  # 이 인스턴스가 이전 설정으로 한 번 로그인했다
    await given_directory_settings_changed_in_database(api, base_dn="dc=changed,dc=test")
    # When
    response = await when_log_in(api)
    # Then
    then_status_is(response, 200)
    then_directory_was_asked_with_base_dn(api, "dc=changed,dc=test")


async def test_registered_user_logs_in_through_service_account_search(api: Api) -> None:
    """Scenario: 저장된 Base DN으로 사용자를 찾아 인증하고, 성공하면 비밀번호 해시가 남는다."""
    # Given
    await given_employee(api)
    api.directory.authenticate_calls.clear()
    api.directory.discover_calls.clear()
    # When
    response = await when_log_in(api)
    # Then
    then_signed_in_as(response, subject="kim", email="kim@corp.test", name="김영업", role="sales")
    (call,) = api.directory.authenticate_calls
    assert (call.base_dn, call.login_id.value) == (BASE_DN, "kim")
    assert api.directory.discover_calls == []  # 로그인마다 Base DN을 다시 찾지 않는다
    stored = await then_password_hash_is_stored_for(
        api, login_id="kim", password=password_of("kim")
    )
    assert stored not in response.text


async def test_each_successful_login_replaces_the_stored_hash_with_a_new_salt(api: Api) -> None:
    """Scenario: 로그인에 성공할 때마다 같은 비밀번호도 새 솔트의 해시로 덮어쓴다."""
    # Given
    await given_employee(api)
    await when_log_in(api)
    first = await then_password_hash_is_stored_for(api, login_id="kim", password=password_of("kim"))
    # When
    await when_log_in(api)
    # Then
    second = await then_password_hash_is_stored_for(
        api, login_id="kim", password=password_of("kim")
    )
    assert second != first


async def test_a_failed_login_stores_no_hash(api: Api) -> None:
    """Scenario: 비밀번호가 틀린 로그인은 해시를 만들지 않는다."""
    # Given
    await given_employee(api)
    # When
    response = await when_log_in(api, password="wrong-password")  # noqa: S106 - 가짜 값
    # Then
    then_login_failed_with_the_common_401(response)
    await then_no_password_hash_is_stored(api, login_id="kim")
