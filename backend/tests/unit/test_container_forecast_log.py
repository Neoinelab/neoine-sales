"""Forecast 스냅숏 확인 결과의 로그: 저장했을 때만 INFO, 그 밖은 DEBUG."""

import logging
from datetime import UTC, datetime

import pytest

from app.application.forecast.ensure_monthly_snapshot import (
    SnapshotCheckOutcome,
    SnapshotCheckResult,
)
from app.application.forecast.take_snapshot import SnapshotResult
from app.container_forecast import _log_check
from app.domain.forecast.snapshot import YearMonth

SEPT = YearMonth(2026, 9)
TAKEN_AT = datetime(2026, 10, 1, 0, 5, tzinfo=UTC)


def test_taken_check_is_logged_at_info_with_period_and_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """스냅숏을 저장한 확인은 INFO 로그에 기준 월·셀 수·대체 여부·생성 시각을 남긴다."""
    # given: 셀 7개를 새로 저장한 확인 결과
    result = SnapshotCheckResult(
        SnapshotCheckOutcome.TAKEN, SEPT, SnapshotResult(SEPT, TAKEN_AT, 7, False)
    )
    # when: 결과를 로그로 남긴다
    with caplog.at_level(logging.DEBUG, logger="app.container_forecast"):
        returned = _log_check(result)
    # then: 같은 결과를 돌려주고 INFO 로그 한 줄이 문서의 문구다
    assert returned is result
    records = [r for r in caplog.records if r.name == "app.container_forecast"]
    assert [r.levelno for r in records] == [logging.INFO]
    assert records[0].getMessage() == (
        "Forecast 스냅숏 저장 완료: period=2026-09 cell_count=7 replaced=False "
        f"taken_at={TAKEN_AT.isoformat()}"
    )


@pytest.mark.parametrize(
    "outcome", [SnapshotCheckOutcome.ALREADY_EXISTS, SnapshotCheckOutcome.LOCKED_ELSEWHERE]
)
def test_other_outcomes_are_logged_at_debug_only(
    caplog: pytest.LogCaptureFixture, outcome: SnapshotCheckOutcome
) -> None:
    """저장하지 않은 확인(이미 있음·다른 곳이 잠금)은 DEBUG 로그만 남긴다."""
    # given: 저장 없이 끝난 확인 결과
    result = SnapshotCheckResult(outcome, SEPT, None)
    # when: 결과를 로그로 남긴다
    with caplog.at_level(logging.DEBUG, logger="app.container_forecast"):
        _log_check(result)
    # then: DEBUG 로그뿐이다
    records = [r for r in caplog.records if r.name == "app.container_forecast"]
    assert [r.levelno for r in records] == [logging.DEBUG]
