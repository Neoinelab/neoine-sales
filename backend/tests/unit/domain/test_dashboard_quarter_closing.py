"""QuarterClosing.build: 선택 연도의 Q1~Q4 4행, Forecast 열(Lost 제외)별 누적 셀.

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
    """분기 Closing은 항상 Q1~Q4 네 행이다.

    테스트 코드: DSH-014
    """
    # when: 집계 없이 만든다
    closing = QuarterClosing.build(COLUMNS, [])

    # then: 행은 Q1~Q4다
    assert [row.quarter for row in closing.rows] == [1, 2, 3, 4]


def test_quarters_without_deals_have_zero_cells_for_every_column() -> None:
    """Deal이 없는 분기도 모든 열에 0 셀을 가진다.

    테스트 코드: DSH-014
    """
    # when: Q2에만 집계가 있게 만든다
    closing = QuarterClosing.build(COLUMNS, [_bucket(2, "commit", 1, 10)])

    # then: Q1은 Lost를 뺀 모든 열이 0이고 합계도 0이다
    q1 = closing.rows[0]
    assert set(q1.cells) == {"pipeline", "best", "commit", "won"}
    assert all(cell == Tally.ZERO for cell in q1.cells.values())
    assert q1.open_total == Tally.ZERO
    assert q1.total == Tally.ZERO


def test_columns_exclude_lost_and_keep_order() -> None:
    """열은 Lost를 빼고 코드 순서를 지킨다.

    테스트 코드: DSH-014
    """
    # when: 집계 없이 만든다
    closing = QuarterClosing.build(COLUMNS, [])

    # then: Lost 없이 코드 순서다
    assert [c.key for c in closing.columns] == ["pipeline", "best", "commit", "won"]


def test_lost_bucket_is_excluded_from_quarters() -> None:
    """Lost 집계는 어느 칸에도 들지 않는다.

    테스트 코드: DSH-014
    """
    # when: Lost와 Commit 집계로 만든다
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(1, "lost", 5, 999), _bucket(1, "commit", 1, 7)]
    )

    # then: Q1에 Lost 셀이 없고 합계는 Commit뿐이다
    q1 = closing.rows[0]
    assert "lost" not in q1.cells
    assert q1.open_total == Tally(1, 7)
    assert q1.total == Tally(1, 7)


def test_unknown_forecast_key_bucket_is_ignored() -> None:
    """모르는 Forecast key의 집계는 무시한다.

    BDD 밖: 저장소가 코드에 없는 key를 돌려줘도 합계가 어긋나지 않는지 확인한다.
    """
    # when: 모르는 key와 Best 집계로 만든다
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(3, "no_such", 4, 40), _bucket(3, "best", 1, 2)]
    )

    # then: Q3 합계에 모르는 key가 들지 않는다
    assert closing.rows[2].total == Tally(1, 2)


def test_open_total_excludes_won_and_total_includes_won() -> None:
    """Open 합계는 Won을 빼고 합계는 Open + Won이다.

    테스트 코드: DSH-014
    """
    # when: Pipeline·Commit·Won 집계로 만든다
    closing = QuarterClosing.build(
        COLUMNS,
        [
            _bucket(4, "pipeline", 2, 100),
            _bucket(4, "commit", 1, 40),
            _bucket(4, "won", 3, 500),
        ],
    )

    # then: Q4 Open 합계는 3건·140, 합계는 6건·640이다
    q4 = closing.rows[3]
    assert q4.cells["won"] == Tally(3, 500)
    assert q4.open_total == Tally(3, 140)
    assert q4.total == Tally(6, 640)


def test_buckets_of_the_same_quarter_and_key_are_added() -> None:
    """같은 분기·key의 집계는 더해진다.

    BDD 밖: 저장소가 같은 칸을 나눠 돌려줘도 합쳐지는지 확인한다.
    """
    # when: 같은 칸의 집계 둘로 만든다
    closing = QuarterClosing.build(
        COLUMNS, [_bucket(1, "pipeline", 1, 10), _bucket(1, "pipeline", 2, 5)]
    )

    # then: 칸은 합계다
    assert closing.rows[0].cells["pipeline"] == Tally(3, 15)


def test_buckets_are_placed_in_their_own_quarter() -> None:
    """집계는 자기 분기 행에 놓인다.

    테스트 코드: DSH-014
    """
    # when: Q1·Q2·Q4 Commit 집계로 만든다
    closing = QuarterClosing.build(
        COLUMNS,
        [_bucket(1, "commit", 1, 1), _bucket(2, "commit", 1, 2), _bucket(4, "commit", 1, 4)],
    )

    # then: Commit 칸이 분기별로 다르고 Q3는 0이다
    assert [row.cells["commit"] for row in closing.rows] == [
        Tally(1, 1),
        Tally(1, 2),
        Tally.ZERO,
        Tally(1, 4),
    ]


def test_custom_open_code_becomes_quarter_cell() -> None:
    """admin이 추가한 Open 코드는 분기 셀이 되고 Open 합계에 든다.

    테스트 코드: DSH-007
    """
    # given: 순서 3의 Open 코드 Verbal이 들어간 열(from_codes가 order 순으로 준다)
    verbal = ForecastColumn("verbal", "Verbal", ForecastOutcome.OPEN, 3)
    columns = [PIPELINE, BEST, verbal, COMMIT, WON, LOST]

    # when: Q2 Verbal 집계로 만든다
    closing = QuarterClosing.build(columns, [_bucket(2, "verbal", 2, 30)])

    # then: 열에 Verbal이 있고 Q2 셀과 Open 합계에 든다
    assert [c.key for c in closing.columns] == ["pipeline", "best", "verbal", "commit", "won"]
    assert closing.rows[1].cells["verbal"] == Tally(2, 30)
    assert closing.rows[1].open_total == Tally(2, 30)


@pytest.mark.parametrize("quarter", [0, 5, -1])
def test_quarter_out_of_range_raises(quarter: int) -> None:
    """1~4 밖의 분기 집계는 오류다.

    BDD 밖: 저장소가 잘못된 분기를 돌려주는 버그를 조기에 드러낸다.
    """
    # when·then: 범위 밖 분기 집계로 만들면 ValueError다
    with pytest.raises(ValueError, match=r"."):
        QuarterClosing.build(COLUMNS, [_bucket(quarter, "commit", 1, 1)])
