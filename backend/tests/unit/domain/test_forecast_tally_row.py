"""tally_row (Dashboard 계획 4.1): Forecast 요약과 분기 Closing이 같이 쓰는 셀 계산.

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
    cells, _ = tally_row(COLUMNS, {"commit": Tally(1, 5)})

    assert cells == {"pipeline": Tally.ZERO, "commit": Tally(1, 5), "won": Tally.ZERO}


def test_tally_row_open_total_sums_open_cells_only() -> None:
    cells, open_total = tally_row(
        COLUMNS, {"pipeline": Tally(2, 100), "commit": Tally(1, 40), "won": Tally(3, 500)}
    )

    assert open_total == Tally(3, 140)
    assert cells["won"] == Tally(3, 500)


def test_tally_row_ignores_cells_of_unknown_keys() -> None:
    cells, open_total = tally_row(COLUMNS, {"lost": Tally(9, 999), "pipeline": Tally(1, 1)})

    assert set(cells) == {"pipeline", "commit", "won"}
    assert open_total == Tally(1, 1)


def test_tally_row_without_cells_is_all_zero() -> None:
    cells, open_total = tally_row(COLUMNS, {})

    assert all(cell == Tally.ZERO for cell in cells.values())
    assert open_total == Tally.ZERO
