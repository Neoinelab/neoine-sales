"""NextActionSummary 계약(P2 R1 Minor 1): due_date는 항상 날짜다(NOT NULL)."""

from datetime import date

import pytest
from app.domain.deal_action.next_action_status import NextActionStatus

from app.application.ports.deal_repository import NextActionSummary


def test_summary_with_a_date_keeps_text_and_due_date() -> None:
    summary = NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.DONE
    )

    assert summary.text == "계약서 검토"
    assert summary.due_date == date(2026, 2, 5)
    assert summary.status is NextActionStatus.DONE


def test_summary_without_due_date_is_rejected() -> None:
    with pytest.raises((TypeError, ValueError)):
        NextActionSummary(text="계약서 검토", due_date=None, status=NextActionStatus.OPEN)  # type: ignore[arg-type]
