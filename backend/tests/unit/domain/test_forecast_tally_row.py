"""tally_row: Forecast 요약과 Dashboard 분기 Closing이 같이 쓰는 셀 계산.

columns의 모든 key를 채우고(없으면 ZERO) outcome이 OPEN인 열만 합쳐 open_total로 낸다(Won 제외).
`ForecastSummary.build`의 기존 규칙과 같다.
"""

from app.domain.code.values import ForecastOutcome
from app.domain.forecast.summary import ForecastColumn, Tally, tally_row

PIPELINE = ForecastColumn("pipeline", "Pipeline", ForecastOutcome.OPEN, 1)
COMMIT = ForecastColumn("commit", "Commit", ForecastOutcome.OPEN, 4)
WON = ForecastColumn("won", "Won", ForecastOutcome.WON, 5)
COLUMNS = [PIPELINE, COMMIT, WON]


def test_tally_row_fills_every_column_with_zero_when_missing() -> None:
    """없는 열은 0으로 채운다"""
    # when: 한 열의 집계만 주고 셀을 만든다
    # when: commit 셀만 주고 행을 계산한다
    cells, _ = tally_row(COLUMNS, {"commit": Tally(1, 5)})

    # then: 나머지 열은 0이다
    # then: 모든 열이 있고 없는 열은 0이다
    assert cells == {"pipeline": Tally.ZERO, "commit": Tally(1, 5), "won": Tally.ZERO}


def test_tally_row_open_total_sums_open_cells_only() -> None:
    """Open 합계는 Open 열만 더한다 (Won 제외)"""
    # when: Pipeline·Commit·Won 집계로 셀을 만든다
    # when: pipeline·commit·won 셀로 행을 계산한다
    cells, open_total = tally_row(
        COLUMNS, {"pipeline": Tally(2, 100), "commit": Tally(1, 40), "won": Tally(3, 500)}
    )

    # then: Open 합계는 Pipeline + Commit이고 Won 셀은 그대로다
    # then: Open 합계는 pipeline+commit이고 won 셀은 그대로다
    assert open_total == Tally(3, 140)
    assert cells["won"] == Tally(3, 500)


def test_tally_row_ignores_cells_of_unknown_keys() -> None:
    """열에 없는 key의 셀은 무시한다"""
    # when: 열에 없는 lost 집계가 섞인 채로 셀을 만든다
    # when: lost 셀과 pipeline 셀로 행을 계산한다
    cells, open_total = tally_row(COLUMNS, {"lost": Tally(9, 999), "pipeline": Tally(1, 1)})

    # then: lost는 셀에도 합계에도 없다
    # then: 열 key만 남고 Open 합계는 pipeline 값이다
    assert set(cells) == {"pipeline", "commit", "won"}
    assert open_total == Tally(1, 1)


def test_tally_row_without_cells_is_all_zero() -> None:
    """셀이 없으면 모두 0이다"""
    # when: 빈 집계로 셀을 만든다
    # when: 셀 없이 행을 계산한다
    cells, open_total = tally_row(COLUMNS, {})

    # then: 모두 0이다
    # then: 모든 셀과 Open 합계가 0이다
    assert all(cell == Tally.ZERO for cell in cells.values())
    assert open_total == Tally.ZERO
