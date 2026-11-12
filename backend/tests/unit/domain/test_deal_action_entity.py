"""DealAction 엔티티: 스냅숏·수행 정보는 불변, 내용만 고침, 담당자 확인, 상태."""

from datetime import date

import pytest

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
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
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
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID, uid

EDIT_FORBIDDEN = "본인 Action 또는 admin만 수정할 수 있습니다."
DELETE_FORBIDDEN = "본인 Action 또는 admin만 삭제할 수 있습니다."
STATUS_FORBIDDEN = "본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다."


class TestRecord:
    def test_record_keeps_snapshot_actor_and_acted_at(self) -> None:
        """기록하면 스냅숏·담당자·수행 일시가 정해진다.

        테스트 코드: AC-001
        """
        # given: 제품소개·Best 스냅숏
        snapshot = make_sync("introduction", "best")

        # when: 요청 시각으로 Action을 기록한다
        action = DealAction.record(
            deal_code=make_deal_code("A7K2"),
            content=make_action_content(),
            actor_user_id=ACTOR_ID,
            snapshot=snapshot,
            now=later(5),
            entity_id=DealActionId(new_id()),
        )

        # then: Deal code·담당자·스냅숏이 정해진 값이다
        assert action.deal_code == make_deal_code("A7K2")
        assert action.actor_user_id == ACTOR_ID
        assert action.snapshot == snapshot
        # then: 수행·생성·수정 시각이 모두 요청 시각이다
        assert action.acted_at == action.created_at == action.updated_at == later(5)

    def test_record_uses_the_given_id(self) -> None:
        """기록할 때 준 id를 그대로 쓴다.

        테스트 코드: AC-001
        """
        # given: 정해 둔 Action id
        fixed = DealActionId(new_id())

        # when: 그 id로 기록한다
        action = make_deal_action(entity_id=fixed)
        # then: 같은 id를 가진다
        assert action.id == fixed

    def test_record_requires_an_aware_time(self) -> None:
        """시각대가 없는 시각으로는 기록할 수 없다."""
        # when·then: 시각대 없는 시각으로 기록하면 값 오류다
        with pytest.raises(InvalidValueError):
            make_deal_action(NOW.replace(tzinfo=None))

    def test_the_action_belongs_to_a_deal_by_its_code_and_has_no_free_text_actor(self) -> None:
        """Action은 Deal code로 Deal에 속하고 자유 텍스트 담당자 필드가 없다."""
        # given: Deal code가 있는 Action
        action = make_deal_action(deal_code=make_deal_code("A7K2"))

        # when: Action의 필드를 살펴본다
        deal_code = action.deal_code
        # then: Deal code로 소속되고 예전 필드는 없다
        assert deal_code == make_deal_code("A7K2")
        assert not hasattr(action, "deal_id")
        assert not hasattr(action, "actor")
        assert not hasattr(action, "details")

    def test_a_not_found_error_carries_the_user_message(self) -> None:
        """Action 없음 오류는 사용자용 문구를 가진다.

        테스트 코드: AC-063
        """
        # when·then: Action 없음 오류를 올리면 "Action을 찾을 수 없습니다."다
        with raises_with(DealActionNotFoundError, "Action을 찾을 수 없습니다."):
            raise DealActionNotFoundError(new_id())


class TestRevise:
    def test_revise_replaces_the_content_and_touches_updated_at(self) -> None:
        """내용을 고치면 내용이 바뀌고 수정 시각이 갱신된다.

        테스트 코드: AC-046
        """
        # given: 기본 Action과 바꿀 내용
        action = make_deal_action()
        revised = make_action_content(
            action_type="제안",
            action="제안 발표",
            next_action="견적 회신",
            due_date=date(2026, 2, 1),
            memo="변경",
        )

        # when: 시각을 흘려 내용을 고친다
        changed = action.revise(revised, later(30))

        # then: 바뀌었다고 알리고 내용과 수정 시각이 새 값이다
        assert changed is True
        assert action.content == revised
        assert action.updated_at == later(30)

    def test_revise_does_not_touch_snapshot_actor_or_acted_at(self) -> None:
        """고쳐도 스냅숏·담당자·수행 일시·소속은 바뀌지 않는다.

        테스트 코드: AC-046, AC-035
        """
        # given: 담당자·스냅숏이 정해진 Action
        action = make_deal_action(
            later(5), actor_user_id=uid("kim"), snapshot=make_sync("introduction", "best")
        )
        code, snapshot = action.deal_code, action.snapshot

        # when: 다른 내용으로 고친다
        action.revise(make_action_content(action="다른 내용"), later(900))

        # then: 담당자·스냅숏·수행·생성 시각·소속이 그대로다
        assert action.actor_user_id == uid("kim")
        assert action.snapshot == snapshot
        assert action.acted_at == later(5)
        assert action.created_at == later(5)
        assert action.deal_code == code

    def test_revise_with_same_content_returns_false_and_keeps_updated_at(self) -> None:
        """같은 내용으로 고치면 바뀌지 않았다고 알리고 수정 시각이 그대로다.

        테스트 코드: AC-047
        """
        # given: 기본 Action
        action = make_deal_action()

        # when: 같은 내용으로 고친다
        changed = action.revise(make_action_content(), later(30))

        # then: 변경 없음이고 수정 시각이 그대로다
        assert changed is False
        assert action.updated_at == NOW

    def test_revise_with_content_equal_after_trim_is_not_a_change(self) -> None:
        """앞뒤 공백만 다른 내용은 변경이 아니다.

        테스트 코드: AC-047
        """
        # given: 진행사항 "킥오프"인 Action
        action = make_deal_action(action="킥오프")

        # when: 앞뒤 공백이 붙은 같은 진행사항으로 고친다
        changed = action.revise(make_action_content(action="  킥오프  "), later(30))

        # then: 변경 없음이고 수정 시각이 그대로다
        assert changed is False
        assert action.updated_at == NOW

    def test_revise_with_only_a_new_type_changes_content(self) -> None:
        """유형만 바꿔도 변경이다.

        테스트 코드: AC-053
        """
        # given: 유형 "미팅"인 Action
        action = make_deal_action(action_type="미팅")

        # when: 유형만 "데모"로 고친다
        changed = action.revise(make_action_content(action_type="데모"), later(30))

        # then: 변경이고 유형과 수정 시각이 바뀐다
        assert changed is True
        assert action.content.action_type.name == "데모"
        assert action.updated_at == later(30)

    def test_revise_with_same_type_ref_is_noop(self) -> None:
        """같은 유형 참조로 고치면 변경이 아니다.

        테스트 코드: AC-047
        """
        # given: 유형 "미팅"인 Action
        action = make_deal_action(action_type="미팅")

        # when: 같은 유형 참조로 고친다
        changed = action.revise(make_action_content(action_type=make_type_ref("미팅")), later(30))

        # then: 변경 없음이고 수정 시각이 그대로다
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
        """유형·진행사항·Next Action·Due·Memo 중 하나만 달라도 변경이다.

        테스트 코드: AC-046
        """
        # given: 기본 Action
        action = make_deal_action()

        # when: 한 칸만 바꿔 고친다
        changed = action.revise(make_action_content(**field), later(30))
        # then: 변경으로 판정된다
        assert changed is True


class TestOwnerCheck:
    def test_the_owner_sales_may_edit_and_delete(self) -> None:
        """담당자 sales는 수정·삭제할 수 있다.

        테스트 코드: AC-055
        """
        # given: KIM이 담당자인 Action
        action = make_deal_action(actor_user_id=uid("kim"))

        # when·then: KIM의 수정·삭제 확인이 통과한다
        action.ensure_editable_by(uid("kim"), Role.SALES)
        action.ensure_deletable_by(uid("kim"), Role.SALES)

    def test_admin_may_edit_and_delete_another_users_action(self) -> None:
        """admin은 남의 Action도 수정·삭제할 수 있다.

        테스트 코드: AC-055, AC-061
        """
        # given: KIM이 담당자인 Action
        action = make_deal_action(actor_user_id=uid("kim"))

        # when·then: admin의 수정·삭제 확인이 통과한다
        action.ensure_editable_by(uid("boss"), Role.ADMIN)
        action.ensure_deletable_by(uid("boss"), Role.ADMIN)

    def test_ensure_editable_by_other_sales_raises_forbidden_with_message(self) -> None:
        """다른 sales의 수정은 고정 문구로 거절된다.

        테스트 코드: AC-056
        """
        # given: KIM이 담당자인 Action
        action = make_deal_action(actor_user_id=uid("kim"))

        # when·then: 다른 sales의 수정 확인은 수정 권한 오류다
        with raises_with(DealActionEditForbiddenError, EDIT_FORBIDDEN):
            action.ensure_editable_by(uid("park"), Role.SALES)

    def test_ensure_deletable_by_other_sales_raises_forbidden_with_message(self) -> None:
        """다른 sales의 삭제는 고정 문구로 거절된다.

        테스트 코드: AC-062
        """
        # given: KIM이 담당자인 Action
        action = make_deal_action(actor_user_id=uid("kim"))

        # when·then: 다른 sales의 삭제 확인은 삭제 권한 오류다
        with raises_with(DealActionDeleteForbiddenError, DELETE_FORBIDDEN):
            action.ensure_deletable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_refused_even_for_the_same_id(self) -> None:
        """user 역할은 자기 id의 Action도 수정·삭제할 수 없다.

        테스트 코드: AC-058, AC-064
        """
        # given: 담당자 id가 user 자신인 Action
        action = make_deal_action(actor_user_id=uid("viewer"))

        # when·then: 그 user의 수정 확인이 거절된다
        with pytest.raises(DealActionEditForbiddenError):
            action.ensure_editable_by(uid("viewer"), Role.USER)
        # when·then: 그 user의 삭제 확인도 거절된다
        with pytest.raises(DealActionDeleteForbiddenError):
            action.ensure_deletable_by(uid("viewer"), Role.USER)

    def test_the_forbidden_errors_are_access_denied_errors(self) -> None:
        """수정·삭제 권한 오류는 접근 거부 오류의 한 종류다."""
        # when: 두 오류 클래스의 상속 관계를 확인한다
        # then: 둘 다 접근 거부 오류의 하위 클래스다
        assert issubclass(DealActionEditForbiddenError, AccessDeniedError)
        assert issubclass(DealActionDeleteForbiddenError, AccessDeniedError)


class TestNextActionStateOnRecord:
    def test_record_with_next_action_starts_open(self) -> None:
        """Next Action이 있게 기록하면 Open으로 시작한다.

        테스트 코드: AC-001
        """
        # when: Next Action이 있는 Action을 기록한다
        action = make_deal_action()

        # then: 상태는 Open이고 종료 시각이 없다
        assert action.next_action_state == NextActionState.open()
        assert action.next_action_state is not None
        assert action.next_action_state.status is NextActionStatus.OPEN
        assert action.next_action_state.closed_at is None

    def test_record_progress_only_has_no_state(self) -> None:
        """진행사항만 기록하면 상태가 없다.

        테스트 코드: AC-006
        """
        # when: Next Action 없이 기록한다
        action = make_deal_action(next_action="", due_date=None)

        # then: 상태가 없다
        assert action.next_action_state is None

    def test_record_next_only_starts_open(self) -> None:
        """Next Action만 기록하면 진행사항이 없고 Open으로 시작한다.

        테스트 코드: AC-007
        """
        # when: 진행사항 없이 기록한다
        action = make_deal_action(action="")

        # then: 진행사항은 없고 상태는 Open이다
        assert action.content.action is None
        assert action.next_action_state == NextActionState.open()


class TestReviseNextActionState:
    def test_revise_removing_next_action_clears_state(self) -> None:
        """Next Action을 비워 고치면 상태가 사라진다.

        테스트 코드: AC-050
        """
        # given: Open Next Action이 있는 Action
        action = make_deal_action()

        # when: Next Action과 Due를 비워 고친다
        changed = action.revise(make_action_content(next_action="", due_date=None), later(30))

        # then: 변경이고 상태가 없으며 수정 시각이 바뀐다
        assert changed is True
        assert action.next_action_state is None
        assert action.updated_at == later(30)

    def test_revise_removing_next_action_of_a_closed_one_clears_state_and_time(self) -> None:
        """종료한 Next Action을 비워 고치면 상태와 종료 시각이 사라진다.

        테스트 코드: AC-050
        """
        # given: 종료(수행)로 닫은 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))

        # when: Next Action과 Due를 비워 고친다
        action.revise(make_action_content(next_action="", due_date=None), later(30))

        # then: 상태가 없다
        assert action.next_action_state is None

    def test_revise_adding_next_action_opens(self) -> None:
        """진행사항만 Action에 Next Action을 채우면 Open이 된다.

        테스트 코드: AC-051
        """
        # given: 진행사항만 있는 Action
        action = make_deal_action(next_action="", due_date=None)

        # when: Next Action과 Due를 채워 고친다
        changed = action.revise(make_action_content(), later(30))

        # then: 변경이고 상태는 Open이다
        assert changed is True
        assert action.next_action_state == NextActionState.open()

    def test_revise_changing_closed_next_action_keeps_status(self) -> None:
        """종료한 Next Action의 내용을 고쳐도 상태와 종료 시각은 그대로다.

        테스트 코드: AC-052
        """
        # given: 미수행으로 닫은 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(10))
        closed = action.next_action_state

        # when: Next Action 내용과 Due를 고친다
        action.revise(
            make_action_content(next_action="다른 계획", due_date=date(2026, 3, 1)), later(30)
        )

        # then: 상태와 종료 시각이 그대로다
        assert action.next_action_state == closed
        assert closed is not None
        assert closed.status is NextActionStatus.NOT_DONE
        assert closed.closed_at == later(10)

    def test_revise_progress_only_keeps_a_closed_status(self) -> None:
        """종료한 Action의 진행사항만 고쳐도 종료 상태는 그대로다.

        테스트 코드: AC-052
        """
        # given: 종료(수행)로 닫은 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        closed = action.next_action_state

        # when: 진행사항만 고친다
        action.revise(make_action_content(action="진행 수정"), later(30))

        # then: 종료 상태가 그대로다
        assert action.next_action_state == closed

    def test_revise_with_same_content_keeps_the_state_and_updated_at(self) -> None:
        """같은 내용으로 고치면 상태와 수정 시각이 그대로다.

        테스트 코드: AC-047
        """
        # given: 종료(수행)로 닫은 Action
        action = make_deal_action()
        action.change_next_action_status(NextActionStatus.DONE, "", later(10))
        touched = action.updated_at

        # when·then: 끝의 줄바꿈만 다른 Memo로 고치면 변경 없음이다
        assert action.revise(make_action_content(memo="요구사항 정리\n"), later(30)) is False

        # then: 수정 시각이 그대로다
        assert action.updated_at == touched


class TestStatusOwnerCheck:
    def test_the_owner_sales_and_admin_may_change_the_status(self) -> None:
        """작성자 sales와 admin은 상태를 바꿀 수 있다.

        테스트 코드: NA-012
        """
        # given: sales kim이 작성한 Action
        action = make_deal_action(actor_user_id=uid("kim"))
        # when·then: 작성자 kim과 admin boss가 확인을 통과한다
        action.ensure_status_changeable_by(uid("kim"), Role.SALES)
        action.ensure_status_changeable_by(uid("boss"), Role.ADMIN)

    def test_other_sales_is_refused_with_the_status_message(self) -> None:
        """작성자가 아닌 sales는 상태 변경 고정 문구로 거절된다.

        테스트 코드: NA-013
        """
        # given: sales kim이 작성한 Action
        action = make_deal_action(actor_user_id=uid("kim"))
        # when·then: 다른 sales park의 확인은 고정 문구의 403이다
        with raises_with(DealActionStatusForbiddenError, STATUS_FORBIDDEN):
            action.ensure_status_changeable_by(uid("park"), Role.SALES)

    def test_a_read_only_user_is_refused_even_for_the_same_id(self) -> None:
        """user 역할은 작성자 id가 같아도 상태를 바꿀 수 없다.

        테스트 코드: NA-014
        """
        # given: 작성자 id가 user 역할 사용자 자신인 Action
        action = make_deal_action(actor_user_id=uid("viewer"))
        # when·then: 그 user의 확인은 거절된다
        with pytest.raises(DealActionStatusForbiddenError):
            action.ensure_status_changeable_by(uid("viewer"), Role.USER)

    def test_the_status_forbidden_error_is_an_access_denied_error(self) -> None:
        """상태 변경 거절 오류는 접근 거부 오류의 한 종류다."""
        # when·then: 상속 관계다
        assert issubclass(DealActionStatusForbiddenError, AccessDeniedError)
