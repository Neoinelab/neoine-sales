"""NextActionSummary 계약: due_date는 항상 날짜다(NOT NULL)."""

from datetime import date

import pytest

from app.application.ports.deal_repository import NextActionSummary
from app.domain.deal_action.next_action_status import NextActionStatus


def test_summary_with_a_date_keeps_text_and_due_date() -> None:
    """날짜 기한을 준 요약은 문구·기한·상태를 그대로 가진다."""
    # when: 기한이 날짜인 Next Action 요약을 만든다
    summary = NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.DONE
    )

    # then: 문구·기한·상태가 만들 때의 값 그대로다
    assert summary.text == "계약서 검토"
    assert summary.due_date == date(2026, 2, 5)
    assert summary.status is NextActionStatus.DONE


def test_summary_without_due_date_is_rejected() -> None:
    """기한이 None인 요약은 만들 수 없다."""
    # when·then: due_date=None으로 만들면 오류가 난다
    with pytest.raises((TypeError, ValueError)):
        NextActionSummary(text="계약서 검토", due_date=None, status=NextActionStatus.OPEN)  # type: ignore[arg-type]
