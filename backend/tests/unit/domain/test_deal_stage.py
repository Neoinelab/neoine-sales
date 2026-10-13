"""딜 단계(DealStage)와 Deal.change_stage 규칙: 자유 이동, lost 사유 필수, 같은 단계 금지, 이력."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal.stage import (
    INITIAL_STAGE,
    REASON_MAX,
    DealStage,
    DealStageChange,
    StageChanger,
)
from tests.factories import NOW, later, make_deal, make_deal_details, make_stage_changer

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal

ALL_STAGES = [
    "prospecting",
    "introduction",
    "poc_preparation",
    "poc_completed",
    "technical_evaluation",
    "price_negotiation",
    "contract_completed",
    "lost",
]


def _deal_at(stage: DealStage) -> Deal:
    deal = make_deal()
    if stage is not DealStage.PROSPECTING:
        deal.change_stage(stage, reason="준비", changed_by=make_stage_changer(), now=later(1))
    return deal


class TestDealStage:
    def test_stages_are_the_eight_codes_in_display_order(self) -> None:
        assert [stage.value for stage in DealStage] == ALL_STAGES

    def test_initial_stage_is_prospecting(self) -> None:
        assert INITIAL_STAGE is DealStage.PROSPECTING


class TestStageChanger:
    def test_changer_keeps_subject_and_name(self) -> None:
        changer = StageChanger(subject="u-1", name="김영업")

        assert (changer.subject, changer.name) == ("u-1", "김영업")

    @pytest.mark.parametrize("field", ["subject", "name"])
    def test_changer_text_cannot_be_blank(self, field: str) -> None:
        with pytest.raises(InvalidValueError):
            make_stage_changer(**{field: "   "})

    @pytest.mark.parametrize("field", ["subject", "name"])
    def test_changer_text_is_limited_to_200_chars(self, field: str) -> None:
        make_stage_changer(**{field: "가" * 200})

        with pytest.raises(InvalidValueError):
            make_stage_changer(**{field: "가" * 201})


class TestNewDealStage:
    def test_new_deal_starts_at_prospecting(self) -> None:
        assert make_deal().stage is DealStage.PROSPECTING


class TestChangeStage:
    @pytest.mark.parametrize(
        ("start", "target"),
        [
            (DealStage.CONTRACT_COMPLETED, DealStage.PROSPECTING),
            (DealStage.PROSPECTING, DealStage.PRICE_NEGOTIATION),
            (DealStage.PRICE_NEGOTIATION, DealStage.INTRODUCTION),
            (DealStage.PROSPECTING, DealStage.CONTRACT_COMPLETED),
        ],
    )
    def test_stage_can_move_backward_and_forward_freely(
        self, start: DealStage, target: DealStage
    ) -> None:
        deal = _deal_at(start)

        deal.change_stage(target, reason=None, changed_by=make_stage_changer(), now=later(5))

        assert deal.stage is target

    def test_lost_deal_can_be_reopened_without_reason(self) -> None:
        deal = _deal_at(DealStage.LOST)

        deal.change_stage(
            DealStage.INTRODUCTION, reason=None, changed_by=make_stage_changer(), now=later(5)
        )

        assert deal.stage is DealStage.INTRODUCTION

    def test_change_returns_history_with_from_to_reason_changer_and_time(self) -> None:
        deal = make_deal()
        changer = make_stage_changer(subject="u-7", name="이영업")

        change = deal.change_stage(
            DealStage.POC_PREPARATION, reason="환경 준비", changed_by=changer, now=later(30)
        )

        assert isinstance(change, DealStageChange)
        assert change.deal_id == deal.id
        assert change.from_stage is DealStage.PROSPECTING
        assert change.to_stage is DealStage.POC_PREPARATION
        assert change.reason == "환경 준비"
        assert change.changed_by == changer
        assert change.changed_at == later(30)

    def test_change_touches_updated_at_but_keeps_created_at(self) -> None:
        deal = make_deal()

        deal.change_stage(
            DealStage.INTRODUCTION, reason=None, changed_by=make_stage_changer(), now=later(30)
        )

        assert deal.updated_at == later(30)
        assert deal.created_at == NOW

    def test_each_change_gets_its_own_id(self) -> None:
        deal = make_deal()
        first = deal.change_stage(
            DealStage.INTRODUCTION, reason=None, changed_by=make_stage_changer(), now=later(1)
        )
        second = deal.change_stage(
            DealStage.POC_PREPARATION, reason=None, changed_by=make_stage_changer(), now=later(2)
        )

        assert first.id != second.id
        assert second.from_stage is DealStage.INTRODUCTION

    def test_changing_to_the_same_stage_is_an_invalid_state(self) -> None:
        deal = make_deal()

        with pytest.raises(InvalidStateError):
            deal.change_stage(
                DealStage.PROSPECTING, reason="메모", changed_by=make_stage_changer(), now=later(5)
            )

        assert deal.updated_at == NOW

    def test_same_stage_is_reported_before_the_missing_lost_reason(self) -> None:
        deal = _deal_at(DealStage.LOST)

        with pytest.raises(InvalidStateError):
            deal.change_stage(
                DealStage.LOST, reason=None, changed_by=make_stage_changer(), now=later(5)
            )

    def test_update_keeps_the_stage(self) -> None:
        deal = _deal_at(DealStage.LOST)

        deal.update(
            make_deal_details(
                code=deal.details.code, customer_id=deal.details.customer_id, name="다른 이름"
            ),
            later(9),
        )

        assert deal.stage is DealStage.LOST


class TestStageChangeReason:
    @pytest.mark.parametrize("reason", [None, "", "   "])
    def test_lost_requires_a_reason(self, reason: str | None) -> None:
        deal = make_deal()

        with pytest.raises(InvalidValueError):
            deal.change_stage(
                DealStage.LOST, reason=reason, changed_by=make_stage_changer(), now=later(5)
            )

        assert deal.stage is DealStage.PROSPECTING
        assert deal.updated_at == NOW

    def test_lost_reason_is_trimmed(self) -> None:
        deal = make_deal()

        change = deal.change_stage(
            DealStage.LOST, reason="  예산 부족  ", changed_by=make_stage_changer(), now=later(5)
        )

        assert change.reason == "예산 부족"

    @pytest.mark.parametrize("target", [DealStage.LOST, DealStage.INTRODUCTION])
    def test_reason_is_limited_to_500_chars(self, target: DealStage) -> None:
        make_deal().change_stage(
            target, reason="가" * REASON_MAX, changed_by=make_stage_changer(), now=later(5)
        )

        deal = make_deal()
        with pytest.raises(InvalidValueError):
            deal.change_stage(
                target,
                reason="가" * (REASON_MAX + 1),
                changed_by=make_stage_changer(),
                now=later(5),
            )
        assert deal.stage is DealStage.PROSPECTING

    def test_reason_limit_applies_after_trimming(self) -> None:
        change = make_deal().change_stage(
            DealStage.LOST,
            reason=f"  {'가' * REASON_MAX}  ",
            changed_by=make_stage_changer(),
            now=later(5),
        )

        assert change.reason == "가" * REASON_MAX

    def test_reason_is_optional_memo_for_non_lost_stages(self) -> None:
        memo = make_deal().change_stage(
            DealStage.INTRODUCTION, reason="  메모 ", changed_by=make_stage_changer(), now=later(1)
        )
        blank = make_deal().change_stage(
            DealStage.INTRODUCTION, reason="   ", changed_by=make_stage_changer(), now=later(1)
        )
        empty = make_deal().change_stage(
            DealStage.INTRODUCTION, reason="", changed_by=make_stage_changer(), now=later(1)
        )

        assert memo.reason == "메모"
        assert blank.reason is None
        assert empty.reason is None
