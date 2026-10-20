"""DealAction 엔티티(AC-5·7·14): 스냅숏·수행 정보는 불변, 내용만 고침, 담당자 확인, 상태."""

from datetime import date
from uuid import uuid4

import pytest
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus

from app.domain.auth.errors import AccessDeniedError
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import (
    DealActionDeleteForbiddenError,
    DealActionEditForbiddenError,
    DealActionNotFoundError,
    DealActionStatusForbiddenError,
)
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import (
    NOW,
    later,
    make_action_content,
    make_deal_action,
    make_deal_code,
    make_sync,
)
from tests.factories_action_type import make_type_ref
from tests.support.expect import raises_with
from tests.support.user_ids import ACTOR_ID, uid

EDIT_FORBIDDEN = "본인 Action 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN = "본인 Action 또는 admin만 삭제할 수 있습니다."
STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."


class TestRecord:
    def test_record_keeps_snapshot_actor_and_acted_at(self) -> None:
        snapshot = make_sync("introduction", "best")

        action = DealAction.record(
            deal_code=make_deal_code("A7K2"),
            content=make_action_content(),
            actor_user_id=ACTOR_ID,
            snapshot=snapshot,
            now=later(5),
        )

        assert action.deal_code == make_deal_code("A7K2")
        assert action.actor_user_id == ACTOR_ID
        assert action.snapshot == snapshot
        assert action.acted_at == action.created_at == action.updated_at == later(5)

    def test_record_generates_a_new_id_each_time_unless_one_is_given(self) -> None:
        fixed = DealActionId(uuid4())

        assert make_deal_action().id != make_deal_action().id
        assert make_deal_action(entity_id=fixed).id == fixed

    def test_record_requires_an_aware_time(self) -> None:
        with pytest.raises(InvalidValueError):
            make_deal_action(NOW.replace(tzinfo=None))

    def test_the_action_belongs_to_a_deal_by_its_code_and_has_no_free_text_actor(self) -> None:
        action = make_deal_action(deal_code=make_deal_code("A7K2"))

        assert action.deal_code == make_deal_code("A7K2")
        assert not hasattr(action, "deal_id")
        assert not hasattr(action, "actor")
        assert not hasattr(action, "details")

    def test_a_not_found_error_carries_the_user_message(self) -> None:
        with raises_with(DealActionNotFoundError, "Action을 찾을 수 없습니다."):
            raise DealActionNotFoundError(uuid4())


class TestRevise:
    def test_revise_replaces_the_content_and_touches_updated_at(self) -> None:
        action = make_deal_action()
        revised = make_action_content(
            action_type="제안",
            action="제안 발표",
            next_action="견적 회신",
            due_date=date(2026, 2, 1),
            memo="변경",
        )

        changed = action.revise(revised, later(30))

        assert changed is True
        assert action.content == revised
        assert action.updated_at == later(30)

    def test_revise_does_not_touch_snapshot_actor_or_acted_at(self) -> None:
        action = make_deal_action(
            later(5), actor_user_id=uid("kim"), snapshot=make_sync("introduction", "best")
        )
        code, snapshot = action.deal_code, action.snapshot

        action.revise(make_action_content(action="다른 내용"), later(900))

        assert action.actor_user_id == uid("kim")
        assert action.snapshot == snapshot
        assert action.acted_at == later(5)
        assert action.created_at == later(5)
        assert action.deal_code == code

    def test_revise_with_same_content_returns_false_and_keeps_updated_at(self) -> None:
        action = make_deal_action()

        changed = action.revise(make_action_content(), later(30))

        assert changed is False
        assert action.updated_at == NOW

    def test_revise_with_content_equal_after_trim_is_not_a_change(self) -> None:
        action = make_deal_action(action="킥오프")

        changed = action.revise(make_action_content(action="  킥오프  "), later(30))

        assert changed is False
        assert action.updated_at == NOW

    def test_revise_with_only_a_new_type_changes_content(self) -> None:
        action = make_deal_action(action_type="미팅")

        changed = action.revise(make_action_content(action_type="데모"), later(30))

        assert changed is True
        assert action.content.action_type.name == "데모"
        assert action.updated_at == later(30)

    def test_revise_with_same_type_ref_is_noop(self) -> None:
        action = make_deal_action(action_type="미팅")

        changed = action.revise(make_action_content(action_type=make_type_ref("미팅")), later(30))

        assert changed is False
        assert action.updated_at == NOW

    @pytest.mark.parametrize(
        "field",
        [
            {"action_type": "통화"},
            {"action": "다른 진행"},
            {"next_action": "다른 계획"},
            {"due_date": date(2026, 12, 31)},
            {"memo": "다른 메모"},
        ],
    )
    def test_revise_detects_a_change_in_any_single_field(self, field: dict[str, object]) -> None:
        action = make_deal_action()

        assert action.revise(make_action_content(**field), later(30)) is True


class TestOwnerCheck:
    def test_the_owner_sales_may_edit_and_delete(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        action.ensure_editable_by(uid("kim"), Role.SALES)
        action.ensure_deletable_by(uid("kim"), Role.SALES)

    def test_admin_may_edit_and_delete_another_users_action(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        action.ensure_editable_by(uid("boss"), Role.ADMIN)
        action.ensure_deletable_by(uid("boss"), Role.ADMIN)

    def test_ensure_editable_by_other_sales_raises_forbidden_with_message(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
            action.ensure_editable_by(uid("park"), Role.SALES)

    def test_ensure_deletable_by_other_sales_raises_forbidden_with_message(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        with raises_with(DealActionDeleteForbiddenError, DELETE_FORBIDDEN):
            action.ensure_deletable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_refused_even_for_the_same_id(self) -> None:
        action = make_deal_action(actor_user_id=uid("viewer"))

        with pytest.raises(DealActionEditForbiddenError):
            action.ensure_editable_by(uid("viewer"), Role.USER)
        with pytest.raises(DealActionDeleteForbiddenError):
            action.ensure_deletable_by(uid("viewer"), Role.USER)

    def test_the_forbidden_errors_are_access_denied_errors(self) -> None:
        assert issubclass(DealActionEditForbiddenError, AccessDeniedError)
        assert issubclass(DealActionDeleteForbiddenError, AccessDeniedError)


class TestNextActionStateOnRecord:
    def test_record_with_next_action_starts_open(self) -> None:
        action = make_deal_action()

        assert action.next_action_state == NextActionState.open()
        assert action.next_action_state is not None
        assert action.next_action_state.status is NextActionStatus.OPEN
        assert action.next_action_state.closed_at is None

    def test_record_progress_only_has_no_state(self) -> None:
        action = make_deal_action(next_action="", due_date=None)

        assert action.next_action_state is None

    def test_record_next_only_starts_open(self) -> None:
        action = make_deal_action(action="")

        assert action.content.action is None
        assert action.next_action_state == NextActionState.open()


class TestReviseNextActionState:
    def test_revise_removing_next_action_clears_state(self) -> None:
        action = make_deal_action()

        changed = action.revise(make_action_content(next_action="", due_date=None), later(30))

        assert changed is True
        assert action.next_action_state is None
        assert action.updated_at == later(30)

    def test_revise_removing_next_action_of_a_closed_one_clears_state_and_time(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        action.revise(make_action_content(next_action="", due_date=None), later(30))

        assert action.next_action_state is None

    def test_revise_adding_next_action_opens(self) -> None:
        action = make_deal_action(next_action="", due_date=None)

        changed = action.revise(make_action_content(), later(30))

        assert changed is True
        assert action.next_action_state == NextActionState.open()

    def test_revise_changing_closed_next_action_keeps_status(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))
        closed = action.next_action_state

        action.revise(
            make_action_content(next_action="다른 계획", due_date=date(2026, 3, 1)), later(30)
        )

        assert action.next_action_state == closed
        assert closed is not None
        assert closed.status is NextActionStatus.NOT_DONE
        assert closed.closed_at == later(10)

    def test_revise_progress_only_keeps_a_closed_status(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        closed = action.next_action_state

        action.revise(make_action_content(action="진행 수정"), later(30))

        assert action.next_action_state == closed

    def test_revise_with_same_content_keeps_the_state_and_updated_at(self) -> None:
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        touched = action.updated_at

        assert action.revise(make_action_content(memo="요구사항 정리\n"), later(30)) is False

        assert action.updated_at == touched


class TestStatusOwnerCheck:
    def test_the_owner_sales_and_admin_may_change_the_status(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        action.ensure_status_changeable_by(uid("kim"), Role.SALES)
        action.ensure_status_changeable_by(uid("boss"), Role.ADMIN)

    def test_other_sales_is_refused_with_the_status_message(self) -> None:
        action = make_deal_action(actor_user_id=uid("kim"))

        with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
            action.ensure_status_changeable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_refused_even_for_the_same_id(self) -> None:
        action = make_deal_action(actor_user_id=uid("viewer"))

        with pytest.raises(DealActionStatusForbiddenError):
            action.ensure_status_changeable_by(uid("viewer"), Role.USER)

    def test_the_status_forbidden_error_is_an_access_denied_error(self) -> None:
        assert issubclass(DealActionStatusForbiddenError, AccessDeniedError)
