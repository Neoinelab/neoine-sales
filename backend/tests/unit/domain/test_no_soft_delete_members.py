"""AC5: 어떤 엔티티에도 소프트 삭제 개념(삭제 표시·삭제/복원·삭제 상태 검사)이 없다."""

from typing import TYPE_CHECKING, Any

import pytest

from tests.factories import (
    later,
    make_customer,
    make_customer_details,
    make_deal,
    make_deal_action,
    make_deal_action_details,
    make_deal_details,
    make_partner,
    make_partner_details,
)
from tests.factories_auth import make_user

if TYPE_CHECKING:
    from collections.abc import Callable

SOFT_DELETE_MEMBERS = ("deleted_at", "is_deleted", "soft_delete", "restore", "_ensure_active")
MAKERS: dict[str, Callable[..., Any]] = {
    "customer": make_customer,
    "partner": make_partner,
    "deal": make_deal,
    "deal_action": make_deal_action,
    "user": make_user,
}


@pytest.mark.parametrize("member", SOFT_DELETE_MEMBERS)
@pytest.mark.parametrize("name", MAKERS)
def test_entity_has_no_soft_delete_member(name: str, member: str) -> None:
    entity: Any = MAKERS[name]()

    assert not hasattr(entity, member)
    assert not hasattr(type(entity), member)


def test_customer_update_works_without_any_deletion_state_check() -> None:
    customer = make_customer()

    customer.update(make_customer_details(company_name="바뀐 고객"), later(5))

    assert customer.details.company_name == "바뀐 고객"


def test_partner_update_works_without_any_deletion_state_check() -> None:
    partner = make_partner()

    partner.update(make_partner_details(company_name="바뀐 파트너"), later(5))

    assert partner.details.company_name == "바뀐 파트너"


def test_deal_update_works_without_any_deletion_state_check() -> None:
    deal = make_deal()

    deal.update(
        make_deal_details(
            code=deal.details.code, customer_id=deal.details.customer_id, name="바뀐 딜"
        ),
        later(5),
    )

    assert deal.details.name == "바뀐 딜"


def test_deal_action_update_works_without_any_deletion_state_check() -> None:
    action = make_deal_action()

    action.update(
        make_deal_action_details(deal_id=action.details.deal_id, memo="바뀐 메모"), later(5)
    )

    assert action.details.memo == "바뀐 메모"


def test_user_record_login_works_without_any_deletion_state_check() -> None:
    user = make_user()

    user.record_login(later(5), display_name="김영업", email=None)

    assert user.last_login_at == later(5)
