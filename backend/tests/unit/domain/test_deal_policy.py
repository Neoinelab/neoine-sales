"""Owner 자격(R-5)과 Deal 삭제 권한: 프런트 `canBeOwner`·`canDeleteDeal`과 같다."""

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
    """재직 중인 영업 담당자는 Owner가 될 수 있다."""
    # when·then: 재직 중인 sales를 Owner로 검사한다 → 예외 없이 통과한다
    ensure_owner_eligible(make_user("kim", Role.SALES))  # 예외 없음


@pytest.mark.parametrize("role", [Role.ADMIN, Role.USER])
def test_an_active_admin_or_user_cannot_be_the_owner(role: Role) -> None:
    """재직 중이어도 admin·user는 Owner가 될 수 없다."""
    # when·then: admin 또는 user를 Owner로 검사한다 → "영업 담당자여야 합니다" 입력값 오류다
    with raises_with(InvalidValueError, NOT_SALES_MESSAGE):
        ensure_owner_eligible(make_user("kim", role))


def test_a_missing_user_cannot_be_the_owner() -> None:
    """없는 사용자는 Owner가 될 수 없다."""
    # when·then: None을 Owner로 검사한다 → "영업 담당자여야 합니다" 입력값 오류다
    with raises_with(InvalidValueError, NOT_SALES_MESSAGE):
        ensure_owner_eligible(None)


def test_a_resigned_sales_user_gets_the_resigned_message() -> None:
    """퇴사한 영업 담당자는 퇴사 문구의 오류를 받는다."""
    # when·then: 퇴사한 sales를 Owner로 검사한다 → 퇴사 문구의 입력값 오류다
    with raises_with(InvalidValueError, RESIGNED_MESSAGE):
        ensure_owner_eligible(make_resigned_user("kim", Role.SALES))


@pytest.mark.parametrize("role", [Role.ADMIN, Role.USER])
def test_the_resigned_message_comes_before_the_role_message(role: Role) -> None:
    """퇴사한 사용자는 역할이 달라도 퇴사 문구가 먼저 나온다."""
    # when·then: 퇴사한 admin 또는 user를 Owner로 검사한다 → 역할 문구가 아니라 퇴사 문구의 오류다
    with raises_with(InvalidValueError, RESIGNED_MESSAGE):
        ensure_owner_eligible(make_resigned_user("kim", role))


def test_admin_can_delete_any_deal() -> None:
    """admin은 어떤 Owner의 Deal도 삭제할 수 있다.

    테스트 코드: DD-051
    """
    # when: admin이 다른 Owner의 Deal 삭제 가능 여부를 판정한다
    actual = can_delete_deal(uid("boss"), Role.ADMIN, uid("someone-else"))
    # then: 가능하다
    assert actual is True


def test_sales_can_delete_only_a_deal_they_own() -> None:
    """sales는 자기가 Owner인 Deal만 삭제할 수 있다.

    테스트 코드: DD-050, DD-052
    """
    # when: Owner 본인과 다른 영업의 삭제 가능 여부를 판정한다
    assert can_delete_deal(uid("kim"), Role.SALES, uid("kim")) is True
    # then: 본인 Deal은 가능하고 남의 Deal은 불가능하다
    assert can_delete_deal(uid("kim"), Role.SALES, uid("park")) is False


def test_a_read_only_user_can_never_delete_even_the_same_id() -> None:
    """읽기 전용 user는 Owner 아이디가 같아도 삭제할 수 없다.

    테스트 코드: DD-053
    """
    # when: user의 삭제 가능 여부를 판정한다
    assert can_delete_deal(uid("kim"), Role.USER, uid("kim")) is False
    # then: 모두 불가능하다
    assert can_delete_deal(uid("kim"), Role.USER, uid("park")) is False
