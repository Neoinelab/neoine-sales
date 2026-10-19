"""Owner 자격(R-5, AC-05·17)과 Deal 삭제 권한(AC-27): 프런트 `canBeOwner`·`canDeleteDeal`과 같다."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.policy import can_delete_deal, ensure_owner_eligible
from tests.factories_auth import make_resigned_user, make_user
from tests.support.expect import raises_with
from tests.support.user_ids import uid

RESIGNED_MESSAGE = "퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요."
NOT_SALES_MESSAGE = "Owner는 재직 중인 영업 담당자여야 합니다."


def test_an_active_sales_user_can_be_the_owner() -> None:
    ensure_owner_eligible(make_user("kim", Role.SALES))  # 예외 없음


@pytest.mark.parametrize("role", [Role.ADMIN, Role.USER])
def test_an_active_admin_or_user_cannot_be_the_owner(role: Role) -> None:
    with raises_with(InvalidValueError, NOT_SALES_MESSAGE):
        ensure_owner_eligible(make_user("kim", role))


def test_a_missing_user_cannot_be_the_owner() -> None:
    with raises_with(InvalidValueError, NOT_SALES_MESSAGE):
        ensure_owner_eligible(None)


def test_a_resigned_sales_user_gets_the_resigned_message() -> None:
    with raises_with(InvalidValueError, RESIGNED_MESSAGE):
        ensure_owner_eligible(make_resigned_user("kim", Role.SALES))


@pytest.mark.parametrize("role", [Role.ADMIN, Role.USER])
def test_the_resigned_message_comes_before_the_role_message(role: Role) -> None:
    with raises_with(InvalidValueError, RESIGNED_MESSAGE):
        ensure_owner_eligible(make_resigned_user("kim", role))


def test_admin_can_delete_any_deal() -> None:
    assert can_delete_deal(uid("boss"), Role.ADMIN, uid("someone-else")) is True


def test_sales_can_delete_only_a_deal_they_own() -> None:
    assert can_delete_deal(uid("kim"), Role.SALES, uid("kim")) is True
    assert can_delete_deal(uid("kim"), Role.SALES, uid("park")) is False


def test_a_read_only_user_can_never_delete_even_the_same_id() -> None:
    assert can_delete_deal(uid("kim"), Role.USER, uid("kim")) is False
    assert can_delete_deal(uid("kim"), Role.USER, uid("park")) is False
