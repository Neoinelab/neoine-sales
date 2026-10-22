"""QuarterClosing.build (Dashboard AC-5): 선택 연도의 Q1~Q4 4행, Forecast 열(Lost 제외)별 누적 셀.

셀 계산 규칙은 `ForecastSummary`와 같다: open_total은 OPEN 셀의 합(Won 제외), total은 Open + Won.
"""

import pytest

from app.domain.code.values import ForecastOutcome
from app.domain.dashboard.quarter_closing import QuarterBucket, QuarterClosing
from app.domain.forecast.summary import ForecastColumn, Tally

PIPELINE = ForecastColumn("pipeline", "Pipeline", ForecastOutcome.OPEN, 1)
BEST = ForecastColumn("best", "Best", ForecastOutcome.OPEN, 2)
COMMIT = ForecastColumn("commit", "Commit", ForecastOutcome.OPEN, 4)
WON = ForecastColumn("won", "Won", ForecastOutcome.WON, 5)
LOST = ForecastColumn("lost", "Lost", ForecastOutcome.LOST, 6)
COLUMNS = [PIPELINE, BEST, COMMIT, WON, LOST]


def _bucket(quarter: int, key: str, count: int, amount: int) -> QuarterBucket:
    return QuarterBucket(quarter=quarter, forecast_key=key, tally=Tally(count, amount))


def test_quarter_closing_always_has_four_quarters() -> None:
    closing = QuarterClosing.build(COLUMNS, [])

    assert [row.quarter for row in closing.rows] == [1, 2, 3, 4]


def test_quarters_without_deals_have_zero_cells_for_every_column() -> None:
    closing = QuarterClosing.build(COLUMNS, [_bucket(2, "commit", 1, 10)])

    q1 = closing.rows[0]
    assert set(q1.cells) == {"pipeline", "best", "commit", "won"}
    assert all(cell == Tally.ZERO for cell in q1.cells.values())
    assert q1.open_total == Tally.ZERO
    assert q1.total == Tally.ZERO


def test_columns_exclude_lost_and_keep_order() -> None:
    closing = QuarterClosing.build(COLUMNS, [])

    assert [c.key for c in closing.columns] == ["pipeline", "best", "commit", "won"]


def test_lost_bucket_is_excluded_from_quarters() -> None:
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(1, "lost", 5, 999), _bucket(1, "commit", 1, 7)]
    )

    q1 = closing.rows[0]
    assert "lost" not in q1.cells
    assert q1.open_total == Tally(1, 7)
    assert q1.total == Tally(1, 7)


def test_unknown_forecast_key_bucket_is_ignored() -> None:
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(3, "no_such", 4, 40), _bucket(3, "best", 1, 2)]
    )

    assert closing.rows[2].total == Tally(1, 2)


def test_open_total_excludes_won_and_total_includes_won() -> None:
    closing = QuarterClosing.build(
        COLUMNS,
        [
            _bucket(4, "pipeline", 2, 100),
            _bucket(4, "commit", 1, 40),
            _bucket(4, "won", 3, 500),
        ],
    )

    q4 = closing.rows[3]
    assert q4.cells["won"] == Tally(3, 500)
    assert q4.open_total == Tally(3, 140)
    assert q4.total == Tally(6, 640)


def test_buckets_of_the_same_quarter_and_key_are_added() -> None:
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(1, "pipeline", 1, 10), _bucket(1, "pipeline", 2, 5)]
    )

    assert closing.rows[0].cells["pipeline"] == Tally(3, 15)


def test_buckets_are_placed_in_their_own_quarter() -> None:
    closing = QuarterClosing.build(
        COLUMNS,
        [_bucket(1, "commit", 1, 1), _bucket(2, "commit", 1, 2), _bucket(4, "commit", 1, 4)],
    )

    assert [row.cells["commit"] for row in closing.rows] == [
        Tally(1, 1),
        Tally(1, 2),
        Tally.ZERO,
        Tally(1, 4),
    ]


def test_custom_open_code_becomes_quarter_cell() -> None:
    verbal = ForecastColumn("verbal", "Verbal", ForecastOutcome.OPEN, 3)

    columns = [PIPELINE, BEST, verbal, COMMIT, WON, LOST]  # from_codes가 order 순으로 준다

    closing = QuarterClosing.build(columns, [_bucket(2, "verbal", 2, 30)])

    assert [c.key for c in closing.columns] == ["pipeline", "best", "verbal", "commit", "won"]
    assert closing.rows[1].cells["verbal"] == Tally(2, 30)
    assert closing.rows[1].open_total == Tally(2, 30)


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_quarter_out_of_range_raises(quarter: int) -> None:
    with pytest.raises(ValueError, match=r"."):
        QuarterClosing.build(COLUMNS, [_bucket(quarter, "commit", 1, 1)])
