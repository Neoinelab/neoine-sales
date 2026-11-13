"""DealActionResponse: 진행사항만/Next Action만 있는 Action과 상태·종료일·수행일 직렬화."""

from datetime import date

from app.domain.auth.principal import Role
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.user.value_objects import UserRef
from app.web.schemas.deal_action import DealActionResponse
from tests.factories import later, make_deal_action
from tests.support.user_ids import ACTOR_ID


def _response(
    action: str = "킥오프 미팅", next_action: str = "요구사항 문서 전달", memo: str = ""
) -> dict[str, object]:
    entity = make_deal_action(
        later(5), actor_user_id=ACTOR_ID, action=action, next_action=next_action, memo=memo
    )
    ref = UserRef(id=ACTOR_ID, name="수행자", resigned=False, role=Role.SALES)
    return DealActionResponse.from_entity(entity, {ACTOR_ID: ref}).model_dump(mode="json")


def test_progress_only_action_serializes_nulls_for_the_next_action_fields() -> None:
    """진행사항만 Action은 Next Action 칸이 모두 null로 직렬화된다.

    테스트 코드: AC-002, AC-006
    """
    # when: 진행사항만 있는 Action을 응답으로 바꾼다
    body = _response(next_action="", memo="")

    # then: Next Action·Due·상태·종료일이 null이다
    assert body["action"] == "킥오프 미팅"
    assert body["next_action"] is None
    assert body["due_date"] is None
    assert body["next_action_status"] is None
    assert body["next_action_closed_on"] is None


def test_next_only_action_serializes_a_null_progress_and_open_status() -> None:
    """Next Action만 Action은 진행사항이 null이고 상태가 open이다.

    테스트 코드: AC-002, AC-007
    """
    # when: Next Action만 있는 Action을 응답으로 바꾼다
    body = _response(action="")

    # then: 진행사항은 null이고 Next Action·Due·상태가 채워진다
    assert body["action"] is None
    assert body["next_action"] == "요구사항 문서 전달"
    assert body["due_date"] == "2026-01-15"
    assert body["next_action_status"] == "open"
    assert body["next_action_closed_on"] is None


def test_closed_action_serializes_status_and_closed_date() -> None:
    """종료한 Action은 상태와 종료일(날짜 문자열)을 직렬화한다.

    테스트 코드: AC-002, AC-112, NA-070
    """
    # given: 미수행으로 닫은 Action
    action = make_deal_action(later(5), actor_user_id=ACTOR_ID)
    action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(60))
    ref = UserRef(id=ACTOR_ID, name="수행자", resigned=False, role=Role.SALES)

    # when: 응답으로 바꾼다
    body = DealActionResponse.from_entity(action, {ACTOR_ID: ref}).model_dump(mode="json")

    # then: 상태와 종료일(YYYY-MM-DD)과 Due가 채워지고 시각 키는 없다
    assert body["next_action_status"] == "not_done"
    assert body["next_action_closed_on"] == later(60).astimezone().date().isoformat()
    assert "next_action_closed_at" not in body
    assert body["due_date"] == date(2026, 1, 15).isoformat()


def test_response_has_the_acted_on_date_and_no_acted_at() -> None:
    """응답은 수행일 acted_on(YYYY-MM-DD)을 주고 acted_at 키가 없다.

    테스트 코드: AC-112
    """
    # when: 응답으로 바꾼다
    body = _response()

    # then: acted_on은 요청 시각의 업무 날짜 문자열이고 acted_at이 없다
    assert body["acted_on"] == later(5).astimezone().date().isoformat()
    assert "acted_at" not in body
