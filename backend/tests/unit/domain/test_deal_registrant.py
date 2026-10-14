"""Deal.registered_by_user_id(등록자 users.id): 기본 None, 생성 시 저장, 수정·단계 변경이 유지.

담당자(Deal Owner)는 DealDetails.owner_user_id 이고 등록자와 별개다.
"""

from datetime import UTC, datetime

from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealId
from tests.factories import NOW, later, make_deal, make_deal_details, make_stage_changer
from tests.support.user_ids import OWNER_ID, uid


def test_registered_by_user_id_is_none_by_default() -> None:
    assert make_deal().registered_by_user_id is None


def test_create_keeps_the_registered_by_user_id() -> None:
    deal = Deal.create(make_deal_details(), NOW, registered_by_user_id=uid("u1"))

    assert deal.registered_by_user_id == uid("u1")


def test_registrant_and_owner_are_independent() -> None:
    deal = make_deal(registered_by_user_id=uid("registrant"), owner_user_id=uid("owner2"))

    assert deal.registered_by_user_id == uid("registrant")
    assert deal.details.owner_user_id == uid("owner2")


def test_default_owner_is_the_factory_owner_not_the_registrant() -> None:
    deal = make_deal(registered_by_user_id=uid("registrant"))

    assert deal.details.owner_user_id == OWNER_ID


def test_deal_no_longer_has_the_old_subject_based_owner_user_id() -> None:
    deal = make_deal(registered_by_user_id=uid("u1"))

    assert not hasattr(deal, "owner_user_id")


def test_rebuilding_a_deal_accepts_the_registrant() -> None:
    deal = Deal(
        id=DealId(make_deal().id),
        details=make_deal_details(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        registered_by_user_id=uid("u1"),
    )

    assert deal.registered_by_user_id == uid("u1")


def test_update_does_not_touch_the_registrant() -> None:
    deal = make_deal(registered_by_user_id=uid("u1"))

    deal.update(make_deal_details(name="이름 변경", customer_id=deal.details.customer_id), later(5))

    assert deal.registered_by_user_id == uid("u1")
    assert deal.details.name == "이름 변경"


def test_update_can_change_the_owner_without_touching_the_registrant() -> None:
    deal = make_deal(registered_by_user_id=uid("u1"))

    deal.update(
        make_deal_details(owner_user_id=uid("new-owner"), customer_id=deal.details.customer_id),
        later(5),
    )

    assert deal.details.owner_user_id == uid("new-owner")
    assert deal.registered_by_user_id == uid("u1")


def test_change_stage_does_not_touch_registrant_or_owner() -> None:
    deal = make_deal(registered_by_user_id=uid("u1"))

    deal.change_stage(
        DealStage.INTRODUCTION,
        reason=None,
        changed_by=make_stage_changer(user_id=uid("u2")),
        now=later(5),
    )

    assert deal.registered_by_user_id == uid("u1")
    assert deal.details.owner_user_id == OWNER_ID
