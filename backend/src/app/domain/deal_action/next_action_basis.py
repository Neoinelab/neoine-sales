"""Next Action 기준 행 선택(RK-R1).

지난 Open(상태 open이고 Due가 오늘보다 앞) 행이 있으면 Due가 가장 이른 행(같으면 id가 큰 행),
없으면 Next Action이 있는 행 중 수행일이 가장 늦은 행(같으면 id가 큰 행)이다.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.next_action_status import NextActionStatus


def is_past_due_open(status: NextActionStatus | None, due: date | None, today: date) -> bool:
    """상태가 open이고 Due가 오늘보다 앞이면 참(오늘은 지난 것이 아니다)."""
    return status is not None and not status.is_closed and due is not None and due < today


def _is_past_due_open(action: DealAction, today: date) -> bool:
    state = action.next_action_state
    return is_past_due_open(None if state is None else state.status, action.content.due_date, today)


def pick_next_action_basis(actions: Iterable[DealAction], today: date) -> DealAction | None:
    """기준 행. Next Action이 없는 행은 무시하고 입력은 바꾸지 않는다."""
    candidates = [a for a in actions if a.content.has_next_action]
    overdue = [a for a in candidates if _is_past_due_open(a, today)]
    if overdue:
        return min(overdue, key=lambda a: (a.content.due_date, -int(a.id)))
    if candidates:
        return max(candidates, key=lambda a: (a.acted_on, int(a.id)))
    return None
