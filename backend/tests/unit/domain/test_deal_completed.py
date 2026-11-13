"""완료된 Deal 판정(`is_completed`)과 삭제 자격(`ensure_deletable_by`)의 완료 규칙(DD-R41)."""

import pytest

from app.domain.auth.principal import Role
from app.domain.deal.errors import DealDeleteForbiddenError
from tests.factories import make_deal, make_sync
from tests.support.expect import raises_with
from tests.support.user_ids import uid

CODE = "20261016-A001"
COMPLETED = "완료된 Deal은 관리자만 삭제할 수 있습니다."
OWNER_ONLY = "본인 Deal 또는 admin만 삭제할 수 있습니다."


@pytest.mark.parametrize(
    ("status_key", "forecast_key", "expected"),
    [
        ("contract_completed", "won", True),
        ("price_negotiation", "lost", False),
        ("price_negotiation", "commit", False),
        ("prospecting", "pipeline", False),
        ("poc_completed", "best", False),
    ],
)
def test_only_the_won_forecast_key_is_completed(
    status_key: str, forecast_key: str, expected: bool
) -> None:
    """완료 판정은 Forecast key가 won일 때만 참이다(Lost·진행 중은 거짓)."""
    from app.domain.deal.sync_state import is_completed  # noqa: PLC0415

    # when·then: 상태 조합을 판정한다 → won만 참이다
    assert is_completed(make_sync(status_key, forecast_key)) is expected


def test_the_owner_sales_user_cannot_delete_a_completed_deal() -> None:
    """Owner 영업은 완료된 Deal의 삭제 자격이 없다.

    테스트 코드: DD-118
    """
    from app.domain.deal.errors import DealDeleteCompletedError  # noqa: PLC0415

    # given: kim이 Owner인 Won Deal
    deal = make_deal(
        code=CODE, owner_user_id=uid("kim"), status_key="contract_completed", forecast_key="won"
    )

    # when·then: kim이 확인한다 → 완료 오류다
    with raises_with(DealDeleteCompletedError, COMPLETED):
        deal.ensure_deletable_by(uid("kim"), Role.SALES)


def test_admin_can_delete_a_completed_deal() -> None:
    """admin은 완료된 Deal의 삭제 자격이 있다.

    테스트 코드: DD-119
    """
    # given: Won Deal
    deal = make_deal(code=CODE, status_key="contract_completed", forecast_key="won")

    # when·then: admin이 확인한다 → 오류가 없다
    deal.ensure_deletable_by(uid("boss"), Role.ADMIN)


def test_the_owner_sales_user_can_delete_a_lost_deal() -> None:
    """Owner 영업은 Lost Deal의 삭제 자격이 있다.

    테스트 코드: DD-120
    """
    # given: kim이 Owner인 Lost Deal
    deal = make_deal(
        code=CODE, owner_user_id=uid("kim"), status_key="price_negotiation", forecast_key="lost"
    )

    # when·then: kim이 확인한다 → 오류가 없다
    deal.ensure_deletable_by(uid("kim"), Role.SALES)


def test_another_sales_user_gets_the_owner_refusal_for_a_completed_deal() -> None:
    """다른 영업은 완료된 Deal에서도 Owner 문구 오류가 먼저다.

    테스트 코드: DD-121
    """
    # given: kim이 Owner인 Won Deal
    deal = make_deal(
        code=CODE, owner_user_id=uid("kim"), status_key="contract_completed", forecast_key="won"
    )

    # when·then: park가 확인한다 → "본인 Deal 또는 admin만" 오류다
    with raises_with(DealDeleteForbiddenError, OWNER_ONLY):
        deal.ensure_deletable_by(uid("park"), Role.SALES)
