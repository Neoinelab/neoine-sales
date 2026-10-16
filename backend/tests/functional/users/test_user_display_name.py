"""Feature: admin은 사용자를 등록할 때 표시 이름을 줄 수 있고, AD 로그인 후에는 AD 값이 덮어쓴다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import USERS, given_ad_account, given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.users import (
    log_in,
    then_logins_listed,
    when_register_user,
    when_register_with_body,
)

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration
NAME_MAX = 200


async def _listed(api: Api, login_id: str) -> dict[str, object]:
    response = await api.get(USERS, params={"status": "active"})
    return next(i for i in response.json()["items"] if i["login_id"] == login_id)


def _then_created_with_name(response: Response, expected: str | None) -> None:
    then_status_is(response, 201)
    assert response.json()["display_name"] == expected


async def test_registered_display_name_is_shown_before_the_first_login(api: Api) -> None:
    """Scenario: 표시 이름을 주고 등록하면 응답과 목록에 그 이름이 보이고 로그인 기록은 없다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="kim", role="sales", display_name="김영업")
    # Then
    _then_created_with_name(response, "김영업")
    item = await _listed(api, "kim")
    assert (item["display_name"], item["last_login_at"]) == ("김영업", None)


async def test_ad_login_overwrites_the_registered_display_name(api: Api) -> None:
    """Scenario: 등록 때 준 이름은 사용자가 AD로 로그인하면 AD의 이름으로 바뀐다."""
    # Given
    await given_logged_in_as(api, role="admin")
    await when_register_user(api, login_id="kim", role="sales", display_name="임시 이름")
    given_ad_account(api, login_id="kim", display_name="김영업(AD)")
    # When
    login = await log_in(api, "kim")
    # Then
    then_status_is(login, 200)
    await log_in(api, "root")
    assert (await _listed(api, "kim"))["display_name"] == "김영업(AD)"


@pytest.mark.parametrize("body_extra", [{}, {"display_name": None}])
async def test_registering_without_a_display_name_leaves_it_empty(
    api: Api, body_extra: dict[str, object]
) -> None:
    """Scenario: 이름을 안 주거나 null이면 기존처럼 201이고 이름은 비어 있다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_with_body(
        api, {"login_id": "kim", "role": "sales", **body_extra}
    )
    # Then
    _then_created_with_name(response, None)
    assert (await _listed(api, "kim"))["display_name"] is None


@pytest.mark.parametrize("sent", ["  김영업 ", "김영업"])
async def test_registered_display_name_is_trimmed(api: Api, sent: str) -> None:
    """Scenario: 이름의 앞뒤 공백은 제거되어 저장된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="kim", role="sales", display_name=sent)
    # Then
    _then_created_with_name(response, "김영업")


@pytest.mark.parametrize("blank", ["", "   "])
async def test_blank_display_name_is_stored_as_empty(api: Api, blank: str) -> None:
    """Scenario: 빈 이름이나 공백뿐인 이름은 이름 없음으로 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_with_body(
        api, {"login_id": "kim", "role": "sales", "display_name": blank}
    )
    # Then
    _then_created_with_name(response, None)


async def test_display_name_of_the_maximum_length_is_accepted(api: Api) -> None:
    """Scenario: 200자 이름은 경계값으로 등록된다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(
        api, login_id="kim", role="sales", display_name="가" * NAME_MAX
    )
    # Then
    _then_created_with_name(response, "가" * NAME_MAX)


@pytest.mark.parametrize("name", ["가" * (NAME_MAX + 1), "a\x00b"])
async def test_overlong_or_nul_display_name_is_422_invalid_value(api: Api, name: str) -> None:
    """Scenario: 200자를 넘거나 NUL이 든 이름은 잘라내지 않고 422로 거절되며 등록되지 않는다."""
    # Given
    await given_logged_in_as(api, role="admin")
    # When
    response = await when_register_user(api, login_id="kim", role="sales", display_name=name)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_logins_listed(api, ["root"])
