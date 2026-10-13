"""Deal.owner_user_id(등록 사용자의 subject): 기본 None, 생성 시 저장, 검증, 수정이 유지."""

from datetime import UTC, datetime

import pytest

from app.domain.auth.principal import SUBJECT_MAX
from app.domain.common.errors import InvalidValueError
from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealId
from tests.factories import NOW, later, make_deal, make_deal_details, make_stage_changer


def test_owner_user_id_is_none_by_default() -> None:
    assert make_deal().owner_user_id is None


def test_create_keeps_the_owner_user_id() -> None:
    deal = Deal.create(make_deal_details(), NOW, owner_user_id="u-1")

    assert deal.owner_user_id == "u-1"


def test_create_strips_the_owner_user_id() -> None:
    deal = Deal.create(make_deal_details(), NOW, owner_user_id="  u-1  ")

    assert deal.owner_user_id == "u-1"


def test_owner_user_id_keeps_letter_case() -> None:
    assert make_deal(owner_user_id="Alice@AD").owner_user_id == "Alice@AD"


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_owner_user_id_becomes_none(blank: str) -> None:
    deal = Deal.create(make_deal_details(), NOW, owner_user_id=blank)

    assert deal.owner_user_id is None


def test_owner_user_id_accepts_exactly_the_subject_max_length() -> None:
    assert SUBJECT_MAX == 200

    assert make_deal(owner_user_id="u" * SUBJECT_MAX).owner_user_id == "u" * SUBJECT_MAX


def test_owner_user_id_over_200_chars_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        make_deal(owner_user_id="u" * (SUBJECT_MAX + 1))


def test_rebuilding_a_deal_validates_the_owner_user_id_too() -> None:
    with pytest.raises(InvalidValueError):
        Deal(
            id=DealId(make_deal().id),
            details=make_deal_details(),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            owner_user_id="u" * (SUBJECT_MAX + 1),
        )


def test_update_does_not_touch_the_owner_user_id() -> None:
    deal = make_deal(owner_user_id="u-1")

    deal.update(make_deal_details(name="이름 변경", customer_id=deal.details.customer_id), later(5))

    assert deal.owner_user_id == "u-1"
    assert deal.details.name == "이름 변경"


def test_change_stage_does_not_touch_the_owner_user_id() -> None:
    deal = make_deal(owner_user_id="u-1")

    deal.change_stage(
        DealStage.INTRODUCTION,
        reason=None,
        changed_by=make_stage_changer(subject="u-2"),
        now=later(5),
    )

    assert deal.owner_user_id == "u-1"


def test_deal_details_has_no_owner_user_id() -> None:
    assert not hasattr(make_deal_details(), "owner_user_id")
