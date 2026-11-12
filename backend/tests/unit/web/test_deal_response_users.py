"""Deal 응답의 users: 0도 그대로 나간다(스키마 계약은 test_deal_users_openapi가 고정)."""

import pytest

from app.application.deal.dto import DealView
from app.application.ports.deal_repository import DealListItem
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserRef
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.support.user_ids import OWNER_ID


def _view(users: int) -> DealView:
    deal = make_deal(NOW, users=users)
    return DealView(
        item=DealListItem(
            deal=deal,
            next_action=None,
            last_updated_at=deal.updated_at,
            license_contract_count=0,
            has_issued_license_contract=False,
        ),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=None,
    )


@pytest.mark.parametrize("users", [0, 7])
def test_response_carries_users_as_is(users: int) -> None:
    """Deal 응답이 users 값(0 포함)을 그대로 내보내는지 확인한다."""
    # when: 목록 행과 상세 응답을 만든다
    for response in (
        DealRowResponse.from_view(_view(users)),
        DealDetailResponse.from_view(_view(users)),
    ):
        # then: 두 응답의 users가 입력 값 그대로다
        assert response.model_dump(mode="json")["users"] == users
