"""DealActionResponse(AC-1·2·7·8): 진행사항만/Next Action만 있는 Action과 상태·종료 시각 직렬화."""

from datetime import date, datetime

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
    body = _response(next_action="", memo="")

    assert body["action"] == "킥오프 미팅"
    assert body["next_action"] is None
    assert body["due_date"] is None
    assert body["next_action_status"] is None
    assert body["next_action_closed_at"] is None


def test_next_only_action_serializes_a_null_progress_and_open_status() -> None:
    body = _response(action="")

    assert body["action"] is None
    assert body["next_action"] == "요구사항 문서 전달"
    assert body["due_date"] == "2026-01-15"
    assert body["next_action_status"] == "open"
    assert body["next_action_closed_at"] is None


def test_closed_action_serializes_status_and_closed_time() -> None:
    action = make_deal_action(later(5), actor_user_id=ACTOR_ID)
    action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(60))
    ref = UserRef(id=ACTOR_ID, name="수행자", resigned=False, role=Role.SALES)

    body = DealActionResponse.from_entity(action, {ACTOR_ID: ref}).model_dump(mode="json")

    assert body["next_action_status"] == "not_done"
    assert datetime.fromisoformat(str(body["next_action_closed_at"])) == later(60)
    assert body["due_date"] == date(2026, 1, 15).isoformat()
