"""Feature: 사용자를 가리키는 데이터가 있으면 삭제는 퇴사 처리가 되고, 없으면 물리 삭제된다."""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_user_registered
from tests.functional.steps.common import then_body_is, then_status_is
from tests.functional.steps.rereads import then_user_is_listed_as_resigned
from tests.functional.steps.users import (
    given_signed_in_session,
    id_of,
    then_logins_listed,
    when_delete_user,
    when_login,
)
from tests.functional.steps.users_db import (
    given_user_linked,
    then_no_session_rows,
)
from tests.support.user_links import LINK_KINDS

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_each_kind_of_reference_alone_turns_the_deletion_into_a_resignation(
    api: Api, kind: str
) -> None:
    """Scenario: 어떤 종류든 참조 행이 하나라도 있으면 삭제는 퇴사 처리가 되고 행·이력은 남는다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    await given_user_linked(api, login_id="kim", kind=kind)
    kim_id = await id_of(api, "kim")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_status_is(response, 200)
    then_body_is(response, {"outcome": "resigned"})
    await then_user_is_listed_as_resigned(api, "kim")
    await then_no_session_rows(api, kim_id)


async def test_a_user_without_any_reference_is_physically_deleted_with_the_sessions(
    api: Api,
) -> None:
    """Scenario: 참조 행이 없으면 물리 삭제되어 어떤 상태 목록에도 남지 않고 세션 행도 사라진다."""
    # Given
    await given_signed_in_session(api, login_id="kim", role="sales")
    kim_id = await id_of(api, "kim")
    # When
    response = await when_delete_user(api, kim_id)
    # Then
    then_body_is(response, {"outcome": "deleted"})
    await then_logins_listed(api, ["root"], status="all")
    await then_no_session_rows(api, kim_id)


async def test_a_resigned_user_cannot_log_in_with_a_valid_ad_password(api: Api) -> None:
    """Scenario: 퇴사 처리된 사용자는 AD 비밀번호가 맞아도 로그인할 수 없다."""
    # Given
    await given_user_registered(api, login_id="kim", role="sales")
    await given_user_linked(api, login_id="kim", kind="deal_owner")
    assert (await when_delete_user(api, await id_of(api, "kim"))).status_code == 200
    # When
    response = await when_login(api, "kim")
    # Then
    then_status_is(response, 401)
