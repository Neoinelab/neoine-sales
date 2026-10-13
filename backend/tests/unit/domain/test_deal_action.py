from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal.errors import DealInUseError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import ActionType, DealActionId
from tests.factories import NOW, later, make_deal_action, make_deal_action_details


class TestDealActionDetails:
    def test_text_fields_are_trimmed_and_memo_defaults_to_empty(self) -> None:
        details = make_deal_action_details(
            action="  킥오프  ", actor=" 박영업 ", next_action="  제안서 전달 ", memo="   "
        )

        assert details.action == "킥오프"
        assert details.actor == "박영업"
        assert details.next_action == "제안서 전달"
        assert details.memo == ""

    @pytest.mark.parametrize("field", ["action", "actor", "next_action"])
    def test_required_text_cannot_be_blank(self, field: str) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action_details(**{field: "   "})

    @pytest.mark.parametrize(
        ("field", "limit"),
        [("action", 200), ("next_action", 200), ("actor", 100), ("memo", 4000)],
    )
    def test_text_length_is_limited(self, field: str, limit: int) -> None:
        make_deal_action_details(**{field: "가" * limit})

        with pytest.raises(InvalidValueError):
            make_deal_action_details(**{field: "가" * (limit + 1)})

    @pytest.mark.parametrize("field", ["action", "actor", "next_action", "memo"])
    def test_text_fields_reject_nul(self, field: str) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action_details(**{field: "가\x00나"})

    def test_due_date_rejects_datetime_values(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action_details(due_date=datetime(2026, 1, 15, 9, 0, tzinfo=UTC))

    def test_due_date_may_be_in_the_past_and_before_acted_at(self) -> None:
        details = make_deal_action_details(acted_at=NOW, due_date=date(2020, 1, 1))

        assert details.due_date == date(2020, 1, 1)

    def test_details_without_next_action_and_due_date_can_be_loaded(self) -> None:
        details = make_deal_action_details(next_action=None, due_date=None)

        assert details.next_action is None
        assert details.due_date is None

    @pytest.mark.parametrize("missing", ["next_action", "due_date"])
    def test_require_complete_rejects_missing_plan_fields(self, missing: str) -> None:
        details = make_deal_action_details(**{missing: None})

        with pytest.raises(InvalidValueError):
            details.require_complete()

    def test_require_complete_accepts_full_details(self) -> None:
        make_deal_action_details().require_complete()

    def test_acted_at_requires_a_timezone(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action_details(acted_at=NOW.replace(tzinfo=None))

    def test_action_types_are_a_closed_set(self) -> None:
        assert {t.value for t in ActionType} == {
            "call", "meeting", "email", "demo", "proposal", "negotiation", "contract", "other",
        }  # fmt: skip


class TestDealAction:
    def test_create_sets_audit_timestamps(self) -> None:
        action = make_deal_action(later(5))

        assert action.created_at == action.updated_at == later(5)

    @pytest.mark.parametrize("missing", ["next_action", "due_date"])
    def test_create_requires_next_action_and_due_date(self, missing: str) -> None:
        with pytest.raises(InvalidValueError):
            DealAction.create(make_deal_action_details(**{missing: None}), NOW)

    @pytest.mark.parametrize("missing", ["next_action", "due_date"])
    def test_update_requires_next_action_and_due_date(self, missing: str) -> None:
        action = make_deal_action()
        details = make_deal_action_details(deal_id=action.details.deal_id, **{missing: None})

        with pytest.raises(InvalidValueError):
            action.update(details, later(30))

    def test_legacy_action_without_plan_fields_can_be_restored(self) -> None:
        details = make_deal_action_details(next_action=None, due_date=None)

        restored = DealAction(
            id=DealActionId(uuid4()), details=details, created_at=NOW, updated_at=NOW
        )

        assert restored.details.due_date is None

    def test_update_replaces_fields_and_touches_updated_at(self) -> None:
        action = make_deal_action()
        details = make_deal_action_details(
            deal_id=action.details.deal_id,
            action="제안 발표",
            next_action="견적 회신",
            due_date=date(2026, 2, 1),
            memo="변경",
        )

        action.update(details, later(30))

        assert action.details.action == "제안 발표"
        assert action.details.next_action == "견적 회신"
        assert action.details.due_date == date(2026, 2, 1)
        assert action.details.memo == "변경"
        assert action.updated_at == later(30)
        assert action.created_at == NOW

    def test_update_cannot_move_the_action_to_another_deal(self) -> None:
        action = make_deal_action()

        with pytest.raises(InvalidStateError):
            action.update(make_deal_action_details(deal_id=DealId(uuid4())), later())


def test_deal_in_use_error_is_an_invalid_state_error() -> None:
    error = DealInUseError(DealId(uuid4()))

    assert isinstance(error, InvalidStateError)
    assert "활동 또는 단계 변경 이력" in str(error)
