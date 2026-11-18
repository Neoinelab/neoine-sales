"""Deal 목록 행·상세 응답은 `has_issued_license_contract`를 그대로 내보낸다(AC28)."""

import pytest

from app.application.deal.dto import DealView
from app.application.ports.deal_repository import DealListItem
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserRef
from app.web.schemas.deal_response import DealDetailResponse, DealRowResponse
from tests.factories import NOW, make_deal
from tests.factories_contact import make_customer
from tests.support.user_ids import OWNER_ID


def _view(*, issued: bool) -> DealView:
    deal = make_deal(NOW)
    return DealView(
        item=DealListItem(
            deal=deal,
            next_action=None,
            last_updated_on=deal.created_at.astimezone().date(),
            license_contract_count=1,
            has_issued_license_contract=issued,
            unread_comment_count=0,
        ),
        owner=UserRef(id=OWNER_ID, name="김영업", resigned=False, role=Role.SALES),
        customer=make_customer(),
        partner_contacts={},
        risk=None,
        status_days=0,
        vendor=None,
    )


@pytest.mark.parametrize("issued", [True, False])
def test_row_and_detail_responses_carry_the_flag_as_is(issued: bool) -> None:
    """Deal 목록 행·상세 응답은 발급 여부를 그대로 내보낸다.

    테스트 코드: LC-030
    """
    # when: 행 응답과 상세 응답을 만든다 (전제: 발급 여부가 true 또는 false인 Deal 뷰)
    for response in (
        DealRowResponse.from_view(_view(issued=issued)),
        DealDetailResponse.from_view(_view(issued=issued)),
    ):
        assert response.model_dump(mode="json")["has_issued_license_contract"] is issued
    # then: has_issued_license_contract가 입력과 같다
