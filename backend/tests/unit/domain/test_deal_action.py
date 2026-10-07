from uuid import uuid4

import pytest

from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.value_objects import ActionType
from tests.factories import NOW, later, make_deal_action, make_deal_action_details


class TestDealActionDetails:
    def test_text_fields_are_trimmed_and_content_defaults_to_empty(self) -> None:
        details = make_deal_action_details(title="  킥오프  ", actor=" 박영업 ", content="   ")

        assert details.title == "킥오프"
        assert details.actor == "박영업"
        assert details.content == ""

    @pytest.mark.parametrize("field", ["title", "actor"])
    def test_required_text_cannot_be_blank(self, field: str) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action_details(**{field: "   "})

    @pytest.mark.parametrize(
        ("field", "limit"), [("title", 200), ("actor", 100), ("content", 4000)]
    )
    def test_text_length_is_limited(self, field: str, limit: int) -> None:
        make_deal_action_details(**{field: "가" * limit})

        with pytest.raises(InvalidValueError):
            make_deal_action_details(**{field: "가" * (limit + 1)})

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
        assert not action.is_deleted

    def test_update_replaces_details_and_touches_updated_at(self) -> None:
        action = make_deal_action()
        details = make_deal_action_details(deal_id=action.details.deal_id, title="제안 발표")

        action.update(details, later(30))

        assert action.details.title == "제안 발표"
        assert action.updated_at == later(30)
        assert action.created_at == NOW

    def test_update_cannot_move_the_action_to_another_deal(self) -> None:
        action = make_deal_action()

        with pytest.raises(InvalidStateError):
            action.update(make_deal_action_details(deal_id=DealId(uuid4())), later())

    def test_deleted_action_cannot_be_updated(self) -> None:
        action = make_deal_action()
        action.soft_delete(later())

        with pytest.raises(InvalidStateError):
            action.update(make_deal_action_details(deal_id=action.details.deal_id), later(10))
